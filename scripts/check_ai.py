import json
with open("data/fetched_heroes.json", encoding="utf-8") as f:
    d = json.load(f)
heroes = d.get("heroes", [])
h = heroes[0]
print("武将:", h.get("hero_name"))
print("段落数:", len(h.get("primary_skill", {}).get("paragraphs", [])))
print("AI抽取结果:")
print(json.dumps(h.get("ai_extraction"), ensure_ascii=False, indent=2))
