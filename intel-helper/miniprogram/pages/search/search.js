const app = getApp();

Page({
  data: {
    searchKey: '',
    seasonList: ['所有赛季'],
    seasonIndex: 0,
    results: [],
    loading: false,
    searched: false
  },
  
  onLoad() {
    this.loadSeasons();
  },
  
  // 加载赛季列表
  loadSeasons() {
    app.request({
      url: '/seasons',
      method: 'GET'
    }).then(res => {
      if (res.seasons && res.seasons.length > 0) {
        this.setData({
          seasonList: ['所有赛季', ...res.seasons]
        });
      }
    }).catch(err => {
      console.error('加载赛季失败', err);
    });
  },
  
  onSearchInput(e) {
    this.setData({ searchKey: e.detail.value });
  },
  
  onSeasonChange(e) {
    this.setData({ seasonIndex: e.detail.value });
  },
  
  searchPlayers() {
    const { searchKey, seasonList, seasonIndex } = this.data;
    const season = seasonIndex > 0 ? seasonList[seasonIndex] : '';
    
    this.setData({ loading: true, searched: true });
    
    app.request({
      url: '/players/search',
      method: 'GET',
      data: {
        q: searchKey,
        season: season
      }
    }).then(res => {
      this.setData({
        results: res.results || [],
        loading: false
      });
    }).catch(err => {
      app.showError('搜索失败');
      this.setData({ loading: false });
    });
  },
  
  viewPlayerDetail(e) {
    const playerId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/player-detail/player-detail?id=${playerId}`
    });
  }
});
