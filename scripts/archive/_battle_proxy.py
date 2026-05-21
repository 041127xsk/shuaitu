"""
率土战报抓取脚本 - mitmdump
监听模拟器流量，自动识别战报相关接口并打印结构
"""
from mitmproxy import http, ctx
import json
import sys
from datetime import datetime

# 战报关键词白名单
BATTLE_KEYWORDS = [
    "battle", "report", "战斗", "战报",
    "stzb", "netease", "game",
]

# 记录已发现的接口
found_endpoints = set()
# 战报数据缓存
battle_data = []

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "192.168.0.239"

def is_battle_url(url: str) -> bool:
    """判断 URL 是否可能是战报相关"""
    url_lower = url.lower()
    return any(kw in url_lower for kw in BATTLE_KEYWORDS)

def extract_url_params(url: str) -> dict:
    """提取 URL 参数"""
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    except:
        return {}

def response(flow: http.HTTPFlow):
    """响应回调 - 核心抓取逻辑"""
    url = flow.request.pretty_url

    if not is_battle_url(url):
        return

    # 记录发现的接口
    from urllib.parse import urlparse
    parsed = urlparse(url)
    endpoint = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if endpoint not in found_endpoints:
        found_endpoints.add(endpoint)
        print(f"\n{'='*60}")
        print(f"[★ 新接口发现] {endpoint}")
        print(f"[参数] {json.dumps(extract_url_params(url), ensure_ascii=False)}")
        print(f"{'='*60}")

    # 尝试解析响应体
    try:
        content_type = flow.response.headers.get("content-type", "")
        raw_text = flow.response.text

        if "json" in content_type or url.endswith(".json"):
            data = json.loads(raw_text)
            # 打印结构概览（截断过长内容）
            preview = json.dumps(data, ensure_ascii=False)
            if len(preview) > 500:
                preview = preview[:500] + "...[truncated]"

            print(f"\n[响应 200] {url}")
            print(f"[类型] {content_type}")
            print(f"[数据预览]\n{preview}")

            # 保存到战报数据
            battle_data.append({
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "endpoint": endpoint,
                "data": data
            })
        else:
            print(f"\n[响应 {flow.response.status_code}] {url} ({content_type})")
            if len(raw_text) > 200:
                print(f"[正文预览] {raw_text[:200]}...")

    except json.JSONDecodeError:
        print(f"\n[响应] {url} (非JSON，长度={len(flow.response.text)})")
    except Exception as e:
        print(f"\n[解析错误] {url}: {e}")

def request(flow: http.HTTPFlow):
    """请求回调 - 打印关键请求"""
    url = flow.request.pretty_url
    if is_battle_url(url):
        print(f"\n[→ 请求] {flow.request.method} {url}")

def error(flow: http.HTTPFlow):
    """错误回调"""
    print(f"\n[✗ 连接错误] {flow.request.pretty_url}: {flow.error}")

def done():
    """退出时汇总"""
    print(f"\n\n{'='*60}")
    print(f"[汇总] 共发现 {len(found_endpoints)} 个战报相关接口")
    print(f"[汇总] 共捕获 {len(battle_data)} 条结构化数据")
    print(f"{'='*60}")
    for ep in sorted(found_endpoints):
        print(f"  - {ep}")

if __name__ == "__main__":
    local_ip = get_local_ip()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         率土战报 MITM 抓包工具  v1.0                     ║
╠══════════════════════════════════════════════════════════╣
║  本机IP: {local_ip:<43} ║
║  监听端口: 8080                                         ║
╠══════════════════════════════════════════════════════════╣
║  MUMU模拟器配置:                                        ║
║  设置 → 网络 → 手动代理                                  ║
║    代理地址: {local_ip:<41} ║
║    端口: 8080                                           ║
║  需安装证书后HTTPS才能解密                              ║
╠══════════════════════════════════════════════════════════╣
║  等待战报流量...  (Ctrl+C 停止)                          ║
╚══════════════════════════════════════════════════════════╝
""")
