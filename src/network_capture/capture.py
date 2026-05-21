"""
capture.py - 率土之滨战报网络抓包
==================================
用 mitmproxy 拦截游戏 HTTP 请求，直接获取战报数据。

用法：
    python src/network_capture/capture.py              # 启动抓包（默认端口 8888）
    python src/network_capture/capture.py --port 8888  # 指定端口
    python src/network_capture/capture.py --setup       # 设置模拟器代理
    python src/network_capture/capture.py --remove      # 移除模拟器代理
    python src/network_capture/capture.py --analyze FILE # 分析已抓数据
    python src/network_capture/capture.py --stats        # 查看数据库统计

原理：
    1. 启动 mitmdump 子进程作为代理服务器
    2. 加载自定义 addon 脚本拦截响应
    3. 配置 MuMu 模拟器使用该代理
    4. 游戏翻页时会请求战报 API
    5. 拦截响应，提取战报 JSON 数据
    6. 自动去重后写入 SQLite + JSON 文件
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 项目路径
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 项目模块（延迟导入，仅在非 mitmdump 子进程中使用）
OUTPUT_DIR = ROOT / "data" / "network_capture"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MITMDUMP_PATH = None  # 自动查找


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _find_mitmdump() -> str:
    """查找 mitmdump 可执行文件路径。"""
    import shutil
    # 先查 PATH
    found = shutil.which("mitmdump")
    if found:
        return found
    # Python Scripts 目录
    python_dir = Path(sys.executable).parent / "Scripts"
    candidate = python_dir / "mitmdump.exe"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError("找不到 mitmdump。请先 pip install mitmproxy")


def _make_digest(url: str, timestamp: str) -> str:
    """根据 URL + 时间戳生成去重 digest。"""
    raw = f"{url}|{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# addon 脚本生成（给 mitmdump -s 使用）
# ---------------------------------------------------------------------------

ADDON_TEMPLATE = '''
"""
mitmdump addon - 率土之滨战报抓包
由 capture.py 自动生成，勿手动编辑。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# 项目路径
ROOT = Path(r"{root}")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mitmproxy import http
from src.database import init_battle_reports_db, insert_battle_report, count_battle_reports

OUTPUT_DIR = Path(r"{output_dir}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

captured_data = []
output_file = OUTPUT_DIR / f"capture_{{datetime.now().strftime('%Y%m%d_%H%M%S')}}.json"

stats = {{"total": 0, "matched": 0, "saved": 0, "skipped_dup": 0, "errors": 0}}

api_patterns = {api_patterns}
battle_keywords = {battle_keywords}

db_conn = init_battle_reports_db()
print(f"[DB] SQLite connected, {{count_battle_reports(db_conn)}} existing records")


def _make_digest(url, timestamp):
    import hashlib
    raw = f"{{url}}|{{timestamp}}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def response(flow: http.HTTPFlow):
    global captured_data
    stats["total"] += 1

    url = flow.request.pretty_url
    url_lower = url.lower()
    if not any(p in url_lower for p in api_patterns):
        return

    stats["matched"] += 1

    try:
        content = flow.response.content
        if not content:
            return

        text = content.decode("utf-8", errors="replace")
        text_lower = text.lower()
        if not any(kw in text_lower for kw in battle_keywords):
            return

        timestamp = datetime.now().isoformat()
        digest = _make_digest(url, timestamp)

        try:
            parsed_data = json.loads(text)
        except json.JSONDecodeError:
            parsed_data = text

        data = {{
            "timestamp": timestamp,
            "url": url,
            "method": flow.request.method,
            "status_code": flow.response.status_code,
            "content_type": flow.response.headers.get("content-type", ""),
            "data": parsed_data,
            "raw": text[:5000],
            "digest": digest,
        }}

        captured_data.append(data)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(captured_data, f, indent=2, ensure_ascii=False)

        row_id = insert_battle_report(
            conn=db_conn,
            url=url,
            method=flow.request.method,
            status_code=flow.response.status_code,
            content_type=flow.response.headers.get("content-type", ""),
            data_json=json.dumps(parsed_data, ensure_ascii=False) if isinstance(parsed_data, (dict, list)) else str(parsed_data),
            raw_preview=text[:5000],
            digest=digest,
        )
        if row_id is None:
            stats["skipped_dup"] += 1
            print(f"[DUP] {{url}}")
            return

        stats["saved"] += 1
        print(f"[CAPTURED] {{url}} -> {{stats['saved']}} items")

    except Exception as e:
        stats["errors"] += 1
        print(f"[ERROR] {{e}}")


def done():
    print()
    print("=" * 50)
    print("  Capture Stats")
    print("=" * 50)
    print(f"  Total requests:  {{stats['total']}}")
    print(f"  Matched API:     {{stats['matched']}}")
    print(f"  Saved:           {{stats['saved']}}")
    print(f"  Duplicates:      {{stats['skipped_dup']}}")
    print(f"  Errors:          {{stats['errors']}}")
    print(f"  JSON file:       {{output_file}}")
    print(f"  DB records:      {{count_battle_reports(db_conn)}}")
    print("=" * 50)
'''


def _generate_addon_script() -> str:
    """生成 mitmdump addon 脚本文件，返回路径。"""
    api_patterns = [
        "battle", "report", "war", "fight", "combat",
        "team", "hero", "alliance",
    ]
    battle_keywords = [
        "battle", "report", "hero", "team", "player",
        "result", "win", "lose", "victory", "defeat",
        "武将", "战报", "胜利", "失败", "同盟",
    ]

    content = ADDON_TEMPLATE.format(
        root=str(ROOT).replace("\\", "\\\\"),
        output_dir=str(OUTPUT_DIR).replace("\\", "\\\\"),
        api_patterns=repr(api_patterns),
        battle_keywords=repr(battle_keywords),
    )

    script_path = OUTPUT_DIR / "_mitmdump_addon.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(script_path)


# ---------------------------------------------------------------------------
# 代理设置（复用 EmulatorController）
# ---------------------------------------------------------------------------

def setup_emulator_proxy(port: int = 8888, serial: str = "127.0.0.1:16384"):
    """通过 EmulatorController 设置模拟器代理。"""
    from src.emulator import EmulatorController
    try:
        emu = EmulatorController(serial=serial)
        emu.ensure_connected()
        proxy = f"127.0.0.1:{port}"
        result = emu._run("shell", "settings", "put", "global", "http_proxy", proxy)
        if result.returncode == 0:
            print(f"[OK] Proxy set: {proxy}")
        else:
            stderr = result.stderr.decode("utf-8", errors="replace")
            print(f"[ERROR] Failed to set proxy: {stderr}")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
    except ConnectionError as e:
        print(f"[ERROR] {e}")


def remove_emulator_proxy(serial: str = "127.0.0.1:16384"):
    """通过 EmulatorController 移除模拟器代理。"""
    from src.emulator import EmulatorController
    try:
        emu = EmulatorController(serial=serial)
        emu.ensure_connected()
        result = emu._run("shell", "settings", "delete", "global", "http_proxy")
        if result.returncode == 0:
            print("[OK] Proxy removed")
        else:
            stderr = result.stderr.decode("utf-8", errors="replace")
            print(f"[ERROR] Failed to remove proxy: {stderr}")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
    except ConnectionError as e:
        print(f"[ERROR] {e}")


# ---------------------------------------------------------------------------
# 启动代理（mitmdump 子进程）
# ---------------------------------------------------------------------------

def start_proxy(port: int = 8888):
    """启动 mitmdump 子进程抓包。"""
    mitmdump = _find_mitmdump()
    addon_script = _generate_addon_script()

    print(f"Starting proxy on 0.0.0.0:{port}")
    print(f"Set emulator proxy to: 127.0.0.1:{port}")
    print(f"Press Ctrl+C to stop\n")

    cmd = [mitmdump, "-p", str(port), "-s", addon_script, "-q"]

    try:
        proc = subprocess.run(cmd, cwd=str(ROOT))
    except KeyboardInterrupt:
        print("\nStopped.")


# ---------------------------------------------------------------------------
# 分析功能
# ---------------------------------------------------------------------------

def analyze_capture(file_path: str):
    """分析已抓取的 JSON 数据文件。"""
    from urllib.parse import urlparse

    path = Path(file_path)
    if not path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\nFile: {file_path}")
    print(f"Total entries: {len(data)}")

    urls = {}
    methods = {}
    status_codes = {}
    for item in data:
        url = item.get("url", "")
        parsed = urlparse(url)
        key = f"{parsed.netloc}{parsed.path}"
        urls[key] = urls.get(key, 0) + 1
        m = item.get("method", "GET")
        methods[m] = methods.get(m, 0) + 1
        sc = item.get("status_code", 0)
        status_codes[sc] = status_codes.get(sc, 0) + 1

    print(f"\n--- URL Distribution ---")
    for url, count in sorted(urls.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}x  {url}")

    print(f"\n--- Methods ---")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}x  {method}")

    print(f"\n--- Status Codes ---")
    for code, count in sorted(status_codes.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}x  {code}")

    print(f"\n--- First 3 Entries ---")
    for i, item in enumerate(data[:3]):
        print(f"\n[{i+1}] {item.get('timestamp', '')}")
        print(f"    URL: {item.get('url', '')}")
        print(f"    Status: {item.get('status_code', '')}")
        raw = item.get("raw", "")
        if len(raw) > 300:
            print(f"    Data: {raw[:300]}...")
        else:
            print(f"    Data: {raw}")


def show_db_stats():
    """显示数据库中的抓包统计。"""
    from src.database import init_battle_reports_db, count_battle_reports, get_battle_reports
    conn = init_battle_reports_db()
    total = count_battle_reports(conn)
    print(f"\nBattle reports in DB: {total}")

    if total > 0:
        reports = get_battle_reports(conn, limit=5)
        print(f"\nLatest 5:")
        for r in reports:
            print(f"  [{r['created_at']}] {r['method']} {r['url']} -> {r['status_code']}")
    conn.close()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="STZ Battle Report Network Capture")
    parser.add_argument("--port", type=int, default=8888, help="Proxy port (default: 8888)")
    parser.add_argument("--analyze", type=str, help="Analyze captured JSON file")
    parser.add_argument("--stats", action="store_true", help="Show DB stats")
    parser.add_argument("--setup", action="store_true", help="Set emulator proxy")
    parser.add_argument("--remove", action="store_true", help="Remove emulator proxy")
    parser.add_argument("--serial", type=str, default="127.0.0.1:16384", help="Emulator ADB serial")

    args = parser.parse_args()

    if args.analyze:
        analyze_capture(args.analyze)
    elif args.stats:
        show_db_stats()
    elif args.setup:
        setup_emulator_proxy(port=args.port, serial=args.serial)
    elif args.remove:
        remove_emulator_proxy(serial=args.serial)
    else:
        start_proxy(port=args.port)
