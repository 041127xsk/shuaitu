const app = getApp();

// 武将克制关系映射
const HERO_COUNTER_MAP = {
  '马超': { countered_by: ['谋略队', '减伤队'], counters: ['谋略队'] },
  '曹操': { countered_by: ['爆发队'], counters: ['物理队', '谋略队'] },
  '刘备': { countered_by: ['爆发队', '禁疗队'], counters: ['治疗队'] },
  '陆逊': { countered_by: ['肉盾队', '减伤队'], counters: ['肉盾队'] },
  '周瑜': { countered_by: ['控制队'], counters: ['谋略队'] },
  '诸葛亮': { countered_by: ['爆发队'], counters: ['控制队'] },
  '吕布': { countered_by: ['减伤队', '控制队'], counters: ['治疗队'] },
  '司马懿': { countered_by: ['肉盾队'], counters: ['谋略队'] }
};

Page({
  data: {
    heroId: null,
    hero: null,
    loading: false,
    counterInfo: null
  },
  
  onLoad(options) {
    if (options.id) {
      this.setData({ heroId: parseInt(options.id) });
      this.loadHeroDetail();
    }
  },
  
  loadHeroDetail() {
    this.setData({ loading: true });
    
    app.request({
      url: '/heroes',
      method: 'GET'
    }).then(res => {
      const heroes = res.heroes || [];
      const hero = heroes.find(h => h.id === this.data.heroId);
      
      // 获取克制信息
      const counterInfo = hero ? HERO_COUNTER_MAP[hero.name] : null;
      
      this.setData({
        hero,
        counterInfo,
        loading: false
      });
    }).catch(err => {
      app.showError('加载武将详情失败');
      this.setData({ loading: false });
    });
  },
  
  getCampColor(camp) {
    const colors = {
      '魏': '#9c27b0',
      '蜀': '#4caf50',
      '吴': '#2196f3',
      '群': '#ff9800'
    };
    return colors[camp] || '#666';
  }
});
