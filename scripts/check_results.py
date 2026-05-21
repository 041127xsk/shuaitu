import json
with open("data/fetched_heroes.json", encoding="utf-8") as f:
    d = json.load(f)
heroes = d.get("heroes", [])
print(f"抓取数量: {len(heroes)}")
for h in heroes:
    ai = h.get("ai_extraction") or {}
    has_error = bool(h.get("error"))
    has_type = bool(ai.get("skill_type"))
    status = "ERR" if has_error else ("OK" if has_type else "no_ai_data")
    print(f"  {h.get('hero_name', '?')}: {status} | type={ai.get('skill_type') or '-'} | rate={ai.get('trigger_rate') or '-'} | err={h.get('error') or '-'}")
