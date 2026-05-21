const app = getApp();

Page({
  data: {
    heroes: [],
    filteredHeroes: [],
    searchKey: '',
    camps: ['全部', '魏', '蜀', '吴', '群'],
    currentCamp: '全部',
    loading: false
  },
  
  onLoad() {
    this.loadHeroes();
  },
  
  onShow() {
    // 每次显示页面时刷新数据
    if (this.data.heroes.length > 0) {
      this.filterHeroes();
    }
  },
  
  loadHeroes() {
    this.setData({ loading: true });
    
    app.request({
      url: '/heroes',
      method: 'GET'
    }).then(res => {
      const heroes = res.heroes || [];
      this.setData({
        heroes,
        filteredHeroes: heroes,
        loading: false
      });
    }).catch(err => {
      app.showError('加载武将失败');
      this.setData({ loading: false });
    });
  },
  
  onSearchInput(e) {
    this.setData({ searchKey: e.detail.value });
    this.filterHeroes();
  },
  
  filterByCamp(e) {
    const camp = e.currentTarget.dataset.camp;
    this.setData({ currentCamp: camp });
    this.filterHeroes();
  },
  
  filterHeroes() {
    const { heroes, searchKey, currentCamp } = this.data;
    
    let filtered = heroes;
    
    // 搜索过滤
    if (searchKey) {
      filtered = filtered.filter(h => 
        h.name.toLowerCase().includes(searchKey.toLowerCase())
      );
    }
    
    // 阵营过滤
    if (currentCamp !== '全部') {
      filtered = filtered.filter(h => h.camp === currentCamp);
    }
    
    this.setData({ filteredHeroes: filtered });
  },
  
  getCampColor(camp) {
    const colors = {
      '魏': '#9c27b0',
      '蜀': '#4caf50',
      '吴': '#2196f3',
      '群': '#ff9800'
    };
    return colors[camp] || '#666';
  },
  
  viewHeroDetail(e) {
    const heroId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/hero-detail/hero-detail?id=${heroId}`
    });
  }
});
