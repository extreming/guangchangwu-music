var api = require('../../utils/api.js')
var library = require('../../utils/library.js')
var player = require('../../utils/player.js')
var config = require('../../config.js')

Page({
  data: {
    text: '',
    showBox: false,
    busy: false,
    statusText: '',
    statusType: '',
    devHint: false,
    safeBottom: 0,
    nowTitle: '',
    nowLabel: '',
    showNow: false
  },

  onLoad: function () {
    var base = config.apiBase || ''
    var local = base.indexOf('127.0.0.1') >= 0 || base.indexOf('localhost') >= 0
    this.setData({ devHint: local })
  },

  onShow: function () {
    var app = getApp()
    this.setData({ safeBottom: app.globalData.safeBottom || 0 })
    if (this._unsub) this._unsub()
    var that = this
    this._unsub = player.subscribe(function (snap) {
      var show = !!snap.trackId
      var label = snap.playing ? '正在播放，点这里看大按钮' : '点这里继续听'
      var title = snap.title || ''
      if (show === that.data.showNow && label === that.data.nowLabel && title === that.data.nowTitle) return
      that.setData({ showNow: show, nowTitle: title, nowLabel: label })
    })
  },

  onUnload: function () {
    if (this._unsub) this._unsub()
  },

  onShareAppMessage: function () {
    return {
      title: '广场舞音乐，复制链接就能听',
      path: '/pages/index/index'
    }
  },

  setStatus: function (text, type) {
    this.setData({ statusText: text, statusType: type || 'info' })
  },

  showEditor: function () {
    this.setData({ showBox: true })
  },

  onInput: function (e) {
    this.setData({ text: e.detail.value })
  },

  onPaste: function () {
    if (this.data.busy) return
    var that = this
    wx.getClipboardData({
      success: function (res) {
        var text = ((res && res.data) || '').replace(/[\u200b\u200c\u200d\ufeff]/g, '').trim()
        if (!text) {
          that.setData({ showBox: true })
          that.setStatus('剪贴板是空的。请先到抖音或快手点「复制链接」。', 'error')
          return
        }
        that.setData({ text: text })
        if (api.hasUrl(text)) {
          that.setStatus('链接已经贴上了。请点下面的「提取音乐」。', 'ok')
        } else {
          that.setData({ showBox: true })
          that.setStatus('没有看到链接。请复制整段分享文字，里面要有 http。', 'error')
        }
      },
      fail: function (err) {
        var msg = (err && err.errMsg) || ''
        that.setData({ showBox: true })
        if (msg.indexOf('privacy') >= 0) {
          that.setStatus('需要先同意隐私提示，才能自动粘贴。也可以在方框里长按，选择「粘贴」。', 'error')
          return
        }
        that.setStatus('没能读剪贴板。请在方框里长按，选择「粘贴」。', 'error')
      }
    })
  },

  onExtract: function () {
    if (this.data.busy) return
    var text = (this.data.text || '').trim()
    if (!text) {
      this.setData({ showBox: true })
      this.setStatus('请先点「粘贴链接」。', 'error')
      return
    }
    if (!api.hasUrl(text)) {
      this.setData({ showBox: true })
      this.setStatus('这段文字里没有链接。请到抖音或快手，点分享，再点复制链接。', 'error')
      return
    }
    var that = this
    this.setData({
      busy: true,
      statusText: '正在提取音乐，请不要关闭。一首舞曲通常要等十几秒。',
      statusType: 'info'
    })
    api.extract(text).then(function (data) {
      that.setStatus('正在把音乐存进「我的音乐」…', 'info')
      return api.download(data.audio_url).then(function (tempPath) {
        return library.saveFromTemp(tempPath, data)
      })
    }).then(function (track) {
      that.setData({ busy: false, statusText: '', statusType: '' })
      wx.navigateTo({ url: '/pages/player/player?id=' + track.id + '&fresh=1' })
    }).catch(function (err) {
      that.setData({ busy: false })
      that.setStatus((err && err.message) || '提取失败，请稍后再试。', 'error')
    })
  },

  openNow: function () {
    var snap = player.getState()
    if (!snap.trackId) return
    wx.navigateTo({ url: '/pages/player/player?id=' + snap.trackId })
  },

  goLibrary: function () {
    wx.reLaunch({ url: '/pages/library/library' })
  }
})
