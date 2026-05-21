const app = getApp();

Page({
  data: {
    playerId: null,
    playerInfo: null,
    loading: false,
    winCount: 0,
    lossCount: 0,
    showCounterModal: false,
    counterResult: null
  },
  
  onLoad(options) {
    if (options.id) {
      this.setData({ playerId: parseInt(options.id) });
      this.loadPlayerDetail();
    }
  },
  
  loadPlayerDetail() {
    this.setData({ loading: true });
    
    app.request({
      url: `/players/${this.data.playerId}`,
      method: 'GET'
    }).then(res => {
      // 统计胜负
      let winCount = 0, lossCount = 0;
      (res.teams || []).forEach(team => {
        if (team.battle_result === 'win') winCount++;
        else if (team.battle_result === 'loss') lossCount++;
      });
      
      this.setData({
        playerInfo: res,
        winCount,
        lossCount,
        loading: false
      });
    }).catch(err => {
      app.showError('加载玩家详情失败');
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
  },
  
  getHeroCamp(heroName) {
    // 简化版本，实际应从武将库获取
    return '群';
  },
  
  getResultText(result) {
    const texts = {
      'win': '胜利',
      'loss': '失败',
      'draw': '平局',
      'unknown': '未知'
    };
    return texts[result] || '未知';
  },
  
  // 克制分析
  analyzeCounter(e) {
    const teamId = e.currentTarget.dataset.teamId;
    
    app.showLoading('分析中...');
    
    app.request({
      url: '/counter/analyze',
      method: 'POST',
      data: {
        observed_team_id: teamId
      }
    }).then(res => {
      app.hideLoading();
      this.setData({
        showCounterModal: true,
        counterResult: res
      });
    }).catch(err => {
      app.hideLoading();
      app.showError('分析失败');
    });
  },
  
  closeCounterModal() {
    this.setData({
      showCounterModal: false,
      counterResult: null
    });
  }
});
