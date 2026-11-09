var player = require('./utils/player.js')

App({
  globalData: {
    safeBottom: 0,
    platform: 'devtools'
  },
  onLaunch: function () {
    player.init()
    try {
      var sys = wx.getSystemInfoSync()
      var bottom = 0
      if (sys.safeArea && sys.screenHeight) {
        bottom = sys.screenHeight - sys.safeArea.bottom
      }
      this.globalData.safeBottom = bottom > 0 ? bottom : 0
      this.globalData.platform = sys.platform || 'devtools'
    } catch (e) {
      this.globalData.safeBottom = 0
    }
  }
})
