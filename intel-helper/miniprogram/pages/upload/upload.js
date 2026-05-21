const app = getApp();

Page({
  data: {
    tempFilePath: '',
    season: '',
    uploading: false,
    ocrResult: null,
    snapshotId: null,
    
    // 表单数据
    playerName: '',
    alliance: '',
    server: '',
    heroes: ['', '', ''],
    notes: '',
    enemySideIndex: 0,
    enemySideOptions: ['未知', '左侧', '右侧', '上方', '下方'],
    battleResultIndex: 0,
    battleResultOptions: ['未知', '胜利', '失败', '平局']
  },
  
  // 选择图片
  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        this.setData({
          tempFilePath: res.tempFiles[0].tempFilePath
        });
      }
    });
  },
  
  // 赛季输入
  onSeasonInput(e) {
    this.setData({ season: e.detail.value });
  },
  
  // 上传战报
  uploadScreenshot() {
    const { tempFilePath, season } = this.data;
    
    if (!tempFilePath) {
      app.showError('请先选择战报截图');
      return;
    }
    
    if (!season) {
      app.showError('请输入赛季');
      return;
    }
    
    this.setData({ uploading: true });
    
    wx.uploadFile({
      url: `${app.globalData.apiBase}/intel/upload`,
      filePath: tempFilePath,
      name: 'file',
      formData: { season },
      success: (res) => {
        const data = JSON.parse(res.data);
        if (data.success) {
          this.setData({
            ocrResult: data,
            snapshotId: data.snapshot_id,
            'ocrResult.suggested': data.suggested
          });
          // 自动填充识别结果
          if (data.suggested) {
            this.setData({
              playerName: data.suggested.player_name || '',
              alliance: data.suggested.alliance || '',
              heroes: [
                data.suggested.heroes?.[0] || '',
                data.suggested.heroes?.[1] || '',
                data.suggested.heroes?.[2] || ''
              ]
            });
          }
          app.showSuccess('识别完成');
        } else {
          app.showError(data.error || '上传失败');
        }
      },
      fail: (err) => {
        app.showError('网络请求失败');
        console.error(err);
      },
      complete: () => {
        this.setData({ uploading: false });
      }
    });
  },
  
  // 表单输入处理
  onPlayerNameInput(e) {
    this.setData({ playerName: e.detail.value });
  },
  
  onAllianceInput(e) {
    this.setData({ alliance: e.detail.value });
  },
  
  onServerInput(e) {
    this.setData({ server: e.detail.value });
  },
  
  onHeroInput(e) {
    const index = e.currentTarget.dataset.index;
    const heroes = [...this.data.heroes];
    heroes[index] = e.detail.value;
    this.setData({ heroes });
  },
  
  onNotesInput(e) {
    this.setData({ notes: e.detail.value });
  },
  
  onEnemySideChange(e) {
    this.setData({ enemySideIndex: e.detail.value });
  },
  
  onBattleResultChange(e) {
    this.setData({ battleResultIndex: e.detail.value });
  },
  
  // 确认保存
  confirmIntel() {
    const { snapshotId, playerName, season, alliance, server, heroes, notes } = this.data;
    const { enemySideOptions, battleResultOptions, enemySideIndex, battleResultIndex } = this.data;
    
    if (!playerName) {
      app.showError('请输入玩家名');
      return;
    }
    
    if (!season) {
      app.showError('请输入赛季');
      return;
    }
    
    app.showLoading('保存中...');
    
    const heroInputs = heroes.filter(h => h).map((name, index) => ({
      name,
      position: index + 1
    }));
    
    app.request({
      url: '/intel/confirm',
      method: 'POST',
      data: {
        snapshot_id: snapshotId,
        player_name: playerName,
        season: season,
        alliance: alliance || null,
        server: server || null,
        heroes: heroInputs,
        enemy_side: ['unknown', 'left', 'right', 'top', 'bottom'][enemySideIndex],
        battle_result: ['unknown', 'win', 'loss', 'draw'][battleResultIndex],
        notes: notes || null
      }
    }).then(res => {
      app.hideLoading();
      if (res.success) {
        app.showSuccess('保存成功');
        // 重置表单
        this.setData({
          tempFilePath: '',
          season: '',
          ocrResult: null,
          snapshotId: null,
          playerName: '',
          alliance: '',
          server: '',
          heroes: ['', '', ''],
          notes: '',
          enemySideIndex: 0,
          battleResultIndex: 0
        });
      } else {
        app.showError(res.error || '保存失败');
      }
    }).catch(err => {
      app.hideLoading();
      app.showError('保存失败');
      console.error(err);
    });
  }
});
