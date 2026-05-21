/**
 * 小程序入口文件
 */
App({
  globalData: {
    apiBase: 'http://127.0.0.1:8000',
    // apiBase: 'https://your-server-domain.com', // 生产环境
  },
  
  onLaunch() {
    // 检查登录态
    this.checkLoginStatus();
  },
  
  checkLoginStatus() {
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
    }
  },
  
  // 封装的请求方法
  request(options) {
    return new Promise((resolve, reject) => {
      const { apiBase } = this.globalData;
      const url = options.url.startsWith('http') 
        ? options.url 
        : `${apiBase}${options.url}`;
      
      wx.request({
        url,
        method: options.method || 'GET',
        data: options.data || {},
        header: {
          'Content-Type': 'application/json',
          ...options.header
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
          } else {
            reject(res);
          }
        },
        fail: (err) => {
          reject(err);
        }
      });
    });
  },
  
  // 显示加载提示
  showLoading(title = '加载中...') {
    wx.showLoading({
      title,
      mask: true
    });
  },
  
  // 隐藏加载提示
  hideLoading() {
    wx.hideLoading();
  },
  
  // 显示成功提示
  showSuccess(msg) {
    wx.showToast({
      title: msg,
      icon: 'success',
      duration: 2000
    });
  },
  
  // 显示错误提示
  showError(msg) {
    wx.showToast({
      title: msg,
      icon: 'none',
      duration: 2500
    });
  }
})
