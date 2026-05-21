const app = getApp();

Page({
  data: {
    isOnline: false,
    apiBase: ''
  },
  
  onLoad() {
    this.setData({ apiBase: app.globalData.apiBase });
    this.checkServerStatus();
  },
  
  onShow() {
    this.checkServerStatus();
  },
  
  checkServerStatus() {
    wx.request({
      url: `${app.globalData.apiBase}/health`,
      method: 'GET',
      timeout: 5000,
      success: (res) => {
        this.setData({ isOnline: res.statusCode === 200 });
      },
      fail: () => {
        this.setData({ isOnline: false });
      }
    });
  },
  
  goToUpload() {
    wx.switchTab({ url: '/pages/upload/upload' });
  },
  
  goToSearch() {
    wx.switchTab({ url: '/pages/search/search' });
  },
  
  goToHeroes() {
    wx.switchTab({ url: '/pages/heroes/heroes' });
  }
});
