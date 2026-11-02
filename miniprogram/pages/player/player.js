var library = require('../../utils/library.js')
var player = require('../../utils/player.js')
var bridge = require('../../utils/bridge.js')
var format = require('../../utils/format.js')

Page({
  data: {
    track: null,
    missing: false,
    fresh: false,
    playing: false,
    waiting: false,
    loopOn: true,
    playLabel: '播放',
    loopText: '重复播放：开着',
    loopHelp: '播完会自动再来一遍，适合反复练。',
    hint: '点大大的「播放」。音量按手机侧面的按键。',
    timeText: '',
    statusText: '',
    safeBottom: 0
  },

  onLoad: function (query) {
    this.songId = query.id || ''
    this.fresh = query.fresh === '1'
  },

  onShow: function () {
    var app = getApp()
    this.setData({ safeBottom: app.globalData.safeBottom || 0 })
    this.loadTrack()
    if (this._unsub) this._unsub()
    var that = this
    this._unsub = player.subscribe(function (snap) {
      that.applySnap(snap)
    })
  },

  onUnload: function () {
    if (this._unsub) this._unsub()
  },

  loadTrack: function () {
    var track = library.get(this.songId)
    if (!track) {
      this.setData({ track: null, missing: true, fresh: false })
      return
    }
    var exists = library.fileExists(track.filePath)
    this.setData({
      track: track,
      missing: !exists,
      fresh: this.fresh && exists
    })
  },

  applySnap: function (snap) {
    var track = this.data.track
    var mine = track && snap.trackId === track.id
    var loopOn = !!snap.loop
    var current = mine ? snap.current : 0
    var total = mine && snap.duration ? snap.duration : (track && track.duration) || 0
    var timeText = ''
    if (mine && (current > 0 || total > 0)) {
      var left = format.formatDuration(current)
      var right = format.formatDuration(total)
      if (left && right) timeText = '已播放 ' + left + '，一共 ' + right
      else if (right) timeText = '一共 ' + right
    } else if (track && track.duration) {
      timeText = '一共 ' + format.formatDuration(track.duration)
    }
    var waiting = mine && snap.waiting && !snap.playing
    var playing = mine && snap.playing
    this.setData({
      playing: playing,
      waiting: waiting,
      loopOn: loopOn,
      playLabel: waiting ? '请稍等' : (playing ? '暂停' : '播放'),
      loopText: loopOn ? '重复播放：开着' : '重复播放：关着',
      loopHelp: loopOn ? '播完会自动再来一遍，适合反复练。' : '播完就停。想反复练，就点上面打开。',
      hint: mine ? snap.hint : '点大大的「播放」。音量按手机侧面的按键。',
      timeText: timeText
    })
  },

  onToggle: function () {
    if (!this.data.track || this.data.missing) return
    player.toggle(this.data.track)
  },

  onLoop: function () {
    player.setLoop(!this.data.loopOn)
  },

  onShare: function () {
    var track = this.data.track
    if (!track) return
    var that = this
    if (!wx.shareFileMessage) {
      this.copyLink()
      this.setData({ statusText: '这个微信版本不能直接发文件。如果链接已复制，请打开浏览器粘贴。' })
      return
    }
    wx.shareFileMessage({
      filePath: track.filePath,
      fileName: track.fileName || '舞曲.mp3',
      success: function () {
        that.setData({ statusText: '请在名单里点「文件传输助手」。发完后按下一页的图保存。' })
      },
      fail: function (err) {
        var msg = (err && err.errMsg) || ''
        if (msg.indexOf('cancel') >= 0) return
        that.copyLink()
        that.setData({ statusText: '没能发出去。可以点「看图：存到手机」，或打开浏览器粘贴刚复制的链接。' })
      }
    })
  },

  copyLink: function () {
    var track = this.data.track
    if (!track || !track.remoteUrl) return
    wx.setClipboardData({ data: track.remoteUrl })
  },

  onGuide: function () {
    if (!this.data.track) return
    bridge.setTarget(this.data.track.id)
    wx.navigateTo({ url: '/pages/guide/guide' })
  },

  onDelete: function () {
    var that = this
    var id = this.songId
    wx.showModal({
      title: '删掉这首？',
      content: '删掉之后，这首就不能在这里播放了。',
      confirmText: '删掉',
      cancelText: '留下',
      confirmColor: '#7F1D1D',
      success: function (res) {
        if (!res.confirm) return
        player.stopIf(id)
        library.remove(id)
        wx.navigateBack({
          delta: 1,
          fail: function () {
            wx.reLaunch({ url: '/pages/library/library' })
          }
        })
      }
    })
  },

  goLibrary: function () {
    wx.reLaunch({ url: '/pages/library/library' })
  },

  goIndex: function () {
    wx.reLaunch({ url: '/pages/index/index' })
  }
})
