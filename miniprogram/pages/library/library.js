var library = require('../../utils/library.js')
var player = require('../../utils/player.js')

Page({
  data: {
    songs: [],
    safeBottom: 0
  },

  onShow: function () {
    var app = getApp()
    this.setData({ safeBottom: app.globalData.safeBottom || 0 })
    this.refresh()
    if (this._unsub) this._unsub()
    var that = this
    this._playingId = null
    this._unsub = player.subscribe(function (snap) {
      var id = snap.playing ? snap.trackId : ''
      if (id === that._playingId) return
      that._playingId = id
      that.refresh()
    })
  },

  onUnload: function () {
    if (this._unsub) this._unsub()
  },

  refresh: function () {
    var snap = player.getState()
    this.setData({ songs: library.decorate(library.readAll(), snap.playing ? snap.trackId : '') })
  },

  openSong: function (e) {
    var id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/player/player?id=' + id })
  },

  goIndex: function () {
    wx.reLaunch({ url: '/pages/index/index' })
  }
})
