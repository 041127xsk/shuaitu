
"""
mitmdump addon - 率土之滨战报抓包
由 capture.py 自动生成，勿手动编辑。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# 项目路径
ROOT = Path(r"E:\\openclaw\\openclaw-main")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mitmproxy import http
from src.database import init_battle_reports_db, insert_battle_report, count_battle_reports

OUTPUT_DIR = Path(r"E:\\openclaw\\openclaw-main\\data\\network_capture")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

captured_data = []
output_file = OUTPUT_DIR / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

stats = {"total": 0, "matched": 0, "saved": 0, "skipped_dup": 0, "errors": 0}

api_patterns = ['battle', 'report', 'war', 'fight', 'combat', 'team', 'hero', 'alliance']
battle_keywords = ['battle', 'report', 'hero', 'team', 'player', 'result', 'win', 'lose', 'victory', 'defeat', '武将', '战报', '胜利', '失败', '同盟']

db_conn = init_battle_reports_db()
print(f"[DB] SQLite connected, {count_battle_reports(db_conn)} existing records")


def _make_digest(url, timestamp):
    import hashlib
    raw = f"{url}|{timestamp}"
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

        data = {
            "timestamp": timestamp,
            "url": url,
            "method": flow.request.method,
            "status_code": flow.response.status_code,
            "content_type": flow.response.headers.get("content-type", ""),
            "data": parsed_data,
            "raw": text[:5000],
            "digest": digest,
        }

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
            print(f"[DUP] {url}")
            return

        stats["saved"] += 1
        print(f"[CAPTURED] {url} -> {stats['saved']} items")

    except Exception as e:
        stats["errors"] += 1
        print(f"[ERROR] {e}")


def done():
    print()
    print("=" * 50)
    print("  Capture Stats")
    print("=" * 50)
    print(f"  Total requests:  {stats['total']}")
    print(f"  Matched API:     {stats['matched']}")
    print(f"  Saved:           {stats['saved']}")
    print(f"  Duplicates:      {stats['skipped_dup']}")
    print(f"  Errors:          {stats['errors']}")
    print(f"  JSON file:       {output_file}")
    print(f"  DB records:      {count_battle_reports(db_conn)}")
    print("=" * 50)
