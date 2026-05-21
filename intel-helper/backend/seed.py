"""
数据初始化脚本 - 初始化数据库和基础数据
"""
import os
import sys
from pathlib import Path

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_database, Hero


def seed_heroes():
    """初始化武将数据"""
    db = get_database()

    heroes_data = [
        # 魏国
        {"name": "曹操", "camp": "魏", "troop_type": "骑兵", "attack": 85, "defense": 90, "speed": 72, "tags": "辅助,buff,全队"},
        {"name": "司马懿", "camp": "魏", "troop_type": "骑兵", "attack": 82, "defense": 75, "speed": 70, "tags": "谋略,爆发,持续"},
        {"name": "张辽", "camp": "魏", "troop_type": "骑兵", "attack": 95, "defense": 70, "speed": 95, "tags": "物理,先手,骑兵"},
        {"name": "郭嘉", "camp": "魏", "troop_type": "骑兵", "attack": 70, "defense": 65, "speed": 75, "tags": "谋略,控制,先手"},
        {"name": "荀彧", "camp": "魏", "troop_type": "骑兵", "attack": 68, "defense": 72, "speed": 68, "tags": "谋略,辅助,控制"},
        {"name": "贾诩", "camp": "魏", "troop_type": "骑兵", "attack": 80, "defense": 68, "speed": 72, "tags": "谋略,控制,持续"},
        {"name": "邓艾", "camp": "魏", "troop_type": "骑兵", "attack": 90, "defense": 72, "speed": 85, "tags": "物理,爆发,追击"},
        {"name": "钟会", "camp": "魏", "troop_type": "骑兵", "attack": 88, "defense": 75, "speed": 80, "tags": "物理,控制,辅助"},
        {"name": "曹仁", "camp": "魏", "troop_type": "骑兵", "attack": 75, "defense": 95, "speed": 65, "tags": "物理,肉盾,控制"},
        {"name": "徐晃", "camp": "魏", "troop_type": "骑兵", "attack": 92, "defense": 85, "speed": 70, "tags": "物理,爆发,减伤"},
        {"name": "张郃", "camp": "魏", "troop_type": "弓兵", "attack": 88, "defense": 70, "speed": 82, "tags": "物理,控制,弓兵"},
        {"name": "于禁", "camp": "魏", "troop_type": "步兵", "attack": 78, "defense": 92, "speed": 62, "tags": "物理,肉盾,减伤"},
        {"name": "乐进", "camp": "魏", "troop_type": "骑兵", "attack": 90, "defense": 75, "speed": 88, "tags": "物理,爆发,先手"},

        # 蜀国
        {"name": "刘备", "camp": "蜀", "troop_type": "骑兵", "attack": 72, "defense": 80, "speed": 70, "tags": "治疗,辅助,生存"},
        {"name": "关羽", "camp": "蜀", "troop_type": "骑兵", "attack": 95, "defense": 78, "speed": 85, "tags": "物理,控制,爆发"},
        {"name": "张飞", "camp": "蜀", "troop_type": "骑兵", "attack": 98, "defense": 72, "speed": 80, "tags": "物理,爆发,群攻"},
        {"name": "赵云", "camp": "蜀", "troop_type": "骑兵", "attack": 90, "defense": 85, "speed": 88, "tags": "物理,生存,全能"},
        {"name": "诸葛亮", "camp": "蜀", "troop_type": "弓兵", "attack": 78, "defense": 75, "speed": 70, "tags": "谋略,控制,辅助"},
        {"name": "马超", "camp": "蜀", "troop_type": "骑兵", "attack": 98, "defense": 68, "speed": 95, "tags": "物理,爆发,追击"},
        {"name": "姜维", "camp": "蜀", "troop_type": "骑兵", "attack": 85, "defense": 78, "speed": 75, "tags": "谋略,辅助,控制"},
        {"name": "魏延", "camp": "蜀", "troop_type": "骑兵", "attack": 92, "defense": 75, "speed": 82, "tags": "物理,爆发,战意"},
        {"name": "黄忠", "camp": "蜀", "troop_type": "弓兵", "attack": 95, "defense": 68, "speed": 70, "tags": "物理,弓兵,爆发"},
        {"name": "法正", "camp": "蜀", "troop_type": "弓兵", "attack": 72, "defense": 70, "speed": 68, "tags": "谋略,辅助,治疗"},
        {"name": "庞统", "camp": "蜀", "troop_type": "骑兵", "attack": 75, "defense": 70, "speed": 65, "tags": "谋略,辅助,治疗"},

        # 吴国
        {"name": "孙权", "camp": "吴", "troop_type": "骑兵", "attack": 80, "defense": 82, "speed": 75, "tags": "辅助,生存,全能"},
        {"name": "周瑜", "camp": "吴", "troop_type": "弓兵", "attack": 88, "defense": 68, "speed": 78, "tags": "谋略,控制,群攻"},
        {"name": "陆逊", "camp": "吴", "troop_type": "弓兵", "attack": 90, "defense": 70, "speed": 75, "tags": "谋略,爆发,火攻"},
        {"name": "吕蒙", "camp": "吴", "troop_type": "步兵", "attack": 85, "defense": 82, "speed": 78, "tags": "物理,控制,爆发"},
        {"name": "鲁肃", "camp": "吴", "troop_type": "骑兵", "attack": 65, "defense": 72, "speed": 65, "tags": "谋略,辅助,治疗"},
        {"name": "甘宁", "camp": "吴", "troop_type": "弓兵", "attack": 95, "defense": 70, "speed": 85, "tags": "物理,爆发,暴击"},
        {"name": "太史慈", "camp": "吴", "troop_type": "弓兵", "attack": 92, "defense": 72, "speed": 88, "tags": "物理,连击,弓兵"},
        {"name": "孙策", "camp": "吴", "troop_type": "骑兵", "attack": 95, "defense": 78, "speed": 82, "tags": "物理,爆发,骑兵"},
        {"name": "周泰", "camp": "吴", "troop_type": "步兵", "attack": 82, "defense": 95, "speed": 65, "tags": "物理,保护,肉盾"},
        {"name": "孙坚", "camp": "吴", "troop_type": "步兵", "attack": 85, "defense": 92, "speed": 62, "tags": "物理,肉盾,反击"},
        {"name": "凌统", "camp": "吴", "troop_type": "骑兵", "attack": 88, "defense": 72, "speed": 92, "tags": "物理,先手,辅助"},
        {"name": "朱桓", "camp": "吴", "troop_type": "骑兵", "attack": 90, "defense": 75, "speed": 85, "tags": "物理,爆发,先手"},
        {"name": "丁奉", "camp": "吴", "troop_type": "步兵", "attack": 85, "defense": 82, "speed": 75, "tags": "物理,控制,辅助"},

        # 群雄
        {"name": "吕布", "camp": "群", "troop_type": "骑兵", "attack": 98, "defense": 72, "speed": 88, "tags": "物理,爆发,群攻"},
        {"name": "貂蝉", "camp": "群", "troop_type": "骑兵", "attack": 75, "defense": 70, "speed": 80, "tags": "控制,辅助,混乱"},
        {"name": "张角", "camp": "群", "troop_type": "骑兵", "attack": 85, "defense": 72, "speed": 75, "tags": "谋略,控制,爆发"},
        {"name": "董卓", "camp": "群", "troop_type": "骑兵", "attack": 85, "defense": 90, "speed": 62, "tags": "谋略,控制,肉盾"},
        {"name": "袁绍", "camp": "群", "troop_type": "弓兵", "attack": 85, "defense": 78, "speed": 70, "tags": "谋略,弓兵,控制"},
        {"name": "公孙瓒", "camp": "群", "troop_type": "骑兵", "attack": 82, "defense": 72, "speed": 88, "tags": "谋略,弓兵,辅助"},
        {"name": "华雄", "camp": "群", "troop_type": "骑兵", "attack": 90, "defense": 78, "speed": 80, "tags": "物理,爆发,骑兵"},
        {"name": "李儒", "camp": "群", "troop_type": "弓兵", "attack": 78, "defense": 68, "speed": 72, "tags": "谋略,控制,debuff"},
        {"name": "陈宫", "camp": "群", "troop_type": "弓兵", "attack": 80, "defense": 72, "speed": 70, "tags": "谋略,辅助,控制"},
        {"name": "孟获", "camp": "群", "troop_type": "骑兵", "attack": 85, "defense": 92, "speed": 60, "tags": "肉盾,反击,蛮族"},
        {"name": "祝融", "camp": "群", "troop_type": "骑兵", "attack": 82, "defense": 78, "speed": 75, "tags": "治疗,辅助,蛮族"},
        {"name": "兀突骨", "camp": "群", "troop_type": "步兵", "attack": 78, "defense": 95, "speed": 55, "tags": "肉盾,蛮族,生存"},

        # 其他常见武将
        {"name": "华佗", "camp": "群", "troop_type": "骑兵", "attack": 60, "defense": 68, "speed": 65, "tags": "治疗,辅助,解控"},
        {"name": "蔡文姬", "camp": "魏", "troop_type": "骑兵", "attack": 62, "defense": 70, "speed": 68, "tags": "治疗,辅助,解控"},
        {"name": "甄氏", "camp": "魏", "troop_type": "骑兵", "attack": 65, "defense": 75, "speed": 70, "tags": "辅助,buff,治疗"},
        {"name": "步练师", "camp": "吴", "troop_type": "弓兵", "attack": 68, "defense": 72, "speed": 72, "tags": "治疗,辅助,保护"},
        {"name": "张春华", "camp": "魏", "troop_type": "骑兵", "attack": 70, "defense": 72, "speed": 70, "tags": "治疗,辅助,控制"},
        {"name": "王异", "camp": "魏", "troop_type": "弓兵", "attack": 75, "defense": 70, "speed": 75, "tags": "治疗,辅助,控制"},
        {"name": "大小乔", "camp": "吴", "troop_type": "弓兵", "attack": 62, "defense": 75, "speed": 72, "tags": "辅助,治疗,保护"},
        {"name": "孙武", "camp": "吴", "troop_type": "弓兵", "attack": 78, "defense": 72, "speed": 70, "tags": "谋略,控制,辅助"},
    ]

    with db.get_session() as session:
        # 检查是否已有数据
        existing = session.query(Hero).count()
        if existing > 0:
            print(f"武将数据已存在 ({existing} 条)，跳过初始化")
            return

        # 添加武将
        for hero_data in heroes_data:
            hero = Hero(**hero_data)
            session.add(hero)

        print(f"已添加 {len(heroes_data)} 条武将数据")


def main():
    """主函数"""
    print("=" * 50)
    print("率土战报情报库 - 数据初始化")
    print("=" * 50)

    # 初始化数据库
    print("\n[1/2] 初始化数据库...")
    db = init_database()
    print("数据库表已创建")

    # 初始化武将数据
    print("\n[2/2] 初始化武将数据...")
    seed_heroes()

    print("\n" + "=" * 50)
    print("初始化完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
