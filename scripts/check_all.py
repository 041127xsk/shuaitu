import json
with open("data/fetched_heroes.json", encoding="utf-8") as f:
    d = json.load(f)
heroes = d.get("heroes", [])
for h in heroes:
    name = h.get("hero_name", "?")
    ai = h.get("ai_extraction") or {}
    ps = h.get("primary_skill") or {}
    paras = ps.get("paragraphs") or []
    print(f"【{name}】段落数={len(paras)}")
    print(f"  skill_name: {ai.get('skill_name') or '-'}")
    print(f"  skill_type: {ai.get('skill_type') or '-'}")
    print(f"  trigger_rate: {ai.get('trigger_rate') or '-'}")
    print(f"  trigger_type: {ai.get('trigger_type') or '-'}")
    print(f"  targets: {ai.get('targets') or '-'}")
    print(f"  effects: {ai.get('effects')}")
    print(f"  duration: {ai.get('duration') or '-'}")
    print(f"  notes: {ai.get('notes') or '-'}")
    print()
