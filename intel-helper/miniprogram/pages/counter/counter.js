const app = getApp();

Page({
  data: {
    heroes: ['', '', ''],
    result: null
  },
  
  onHeroInput(e) {
    const index = e.currentTarget.dataset.index;
    const heroes = [...this.data.heroes];
    heroes[index] = e.detail.value;
    this.setData({ heroes });
  },
  
  analyzeTeam() {
    const { heroes } = this.data;
    const validHeroes = heroes.filter(h => h.trim());
    
    if (validHeroes.length === 0) {
      app.showError('请至少输入一个武将');
      return;
    }
    
    // 简化版分析 - 本地实现基础克制逻辑
    this.analyzeLocally(validHeroes);
  },
  
  analyzeLocally(heroNames) {
    // 武将标签映射
    const HERO_TAGS = {
      '马超': ['物理', '爆发', '追击'],
      '关羽': ['物理', '控制', '爆发'],
      '张飞': ['物理', '爆发', '群攻'],
      '赵云': ['物理', '生存', '全能'],
      '刘备': ['治疗', '辅助', '生存'],
      '陆逊': ['谋略', '爆发', '火攻'],
      '周瑜': ['谋略', '控制', '群攻'],
      '诸葛亮': ['谋略', '控制', '辅助'],
      '曹操': ['辅助', 'buff', '全队'],
      '吕布': ['物理', '爆发', '群攻'],
      '司马懿': ['谋略', '爆发', '持续'],
      '孙权': ['辅助', '生存', '全能'],
      '张辽': ['物理', '先手', '骑兵'],
      '华佗': ['治疗', '辅助', '解控'],
      '貂蝉': ['控制', '辅助', '混乱'],
      '甘宁': ['物理', '爆发', '暴击'],
      '太史慈': ['物理', '连击', '弓兵'],
      '孙策': ['物理', '爆发', '骑兵'],
      '周泰': ['物理', '保护', '肉盾'],
      '曹仁': ['物理', '肉盾', '控制'],
      '郭嘉': ['谋略', '控制', '先手'],
      '贾诩': ['谋略', '控制', '持续'],
      '荀彧': ['谋略', '辅助', '控制'],
      '张角': ['谋略', '控制', '爆发'],
      '董卓': ['谋略', '控制', '肉盾'],
      '袁绍': ['谋略', '弓兵', '控制'],
      '姜维': ['谋略', '辅助', '控制'],
      '法正': ['谋略', '辅助', '治疗'],
      '黄忠': ['物理', '弓兵', '爆发'],
      '魏延': ['物理', '爆发', '战意'],
      '孟获': ['肉盾', '反击', '蛮族'],
      '祝融': ['治疗', '辅助', '蛮族']
    };
    
    // 克制关系
    const COUNTER_RELATIONS = {
      '物理': { countered_by: '谋略/减伤队', score: 85, reason: '物理队依赖普通攻击，谋略队和减伤能有效抵消伤害' },
      '谋略': { countered_by: '肉盾/反击队', score: 80, reason: '谋略队多为持续伤害，肉盾队能承受并反击' },
      '爆发': { countered_by: '控制/减伤队', score: 90, reason: '爆发队追求速战，控制和减伤能拖延节奏' },
      '肉盾': { countered_by: '谋略/持续队', score: 85, reason: '肉盾防御高但输出慢，谋略持续伤害能有效突破' },
      '控制': { countered_by: '解控/先手队', score: 88, reason: '控制队依赖封技能，解控和先手能保证输出' },
      '治疗': { countered_by: '爆发/禁疗队', score: 82, reason: '治疗队续航强，需要爆发伤害或禁疗阻止回复' },
      '先手': { countered_by: '后手/反制队', score: 75, reason: '先手队追求速战，后期稳定队形能应对' }
    };
    
    // 收集标签
    let allTags = [];
    heroNames.forEach(name => {
      if (HERO_TAGS[name]) {
        allTags = allTags.concat(HERO_TAGS[name]);
      }
    });
    
    // 统计标签频率
    const tagCount = {};
    allTags.forEach(tag => {
      tagCount[tag] = (tagCount[tag] || 0) + 1;
    });
    
    // 确定队伍类型
    let enemyType = '混兵队';
    const typePriority = ['爆发', '控制', '先手', '治疗', '肉盾', '物理', '谋略'];
    for (const type of typePriority) {
      if (tagCount[type] > 0) {
        enemyType = type + '队';
        break;
      }
    }
    
    // 获取克制建议
    let counter = COUNTER_RELATIONS['物理'];
    for (const key of typePriority) {
      if (tagCount[key] > 0 && COUNTER_RELATIONS[key]) {
        counter = COUNTER_RELATIONS[key];
        break;
      }
    }
    
    // 生成结果
    const result = {
      enemy_team: heroNames,
      enemy_tags: [...new Set(allTags)],
      enemy_type: enemyType,
      recommendations: [
        {
          type: counter.countered_by,
          score: counter.score,
          reason: counter.reason,
          suggested_heroes: this.getSuggestedHeroes(counter.countered_by),
          suggested_tags: counter.countered_by.includes('谋略') ? ['谋略', '减伤', '辅助'] 
                       : counter.countered_by.includes('肉盾') ? ['肉盾', '反击', '减伤']
                       : ['控制', '减伤', '解控']
        }
      ]
    };
    
    this.setData({ result });
  },
  
  getSuggestedHeroes(counterType) {
    const heroesByType = {
      '谋略/减伤队': ['曹操', '刘备', '诸葛亮'],
      '肉盾/反击队': ['曹操', '周泰', '孙坚'],
      '控制/减伤队': ['诸葛亮', '曹操', '刘备'],
      '解控/先手队': ['华佗', '张辽', '甘宁'],
      '爆发/禁疗队': ['马超', '吕布', '张飞'],
      '后手/反制队': ['曹操', '刘备', '周泰']
    };
    return heroesByType[counterType] || [];
  }
});
