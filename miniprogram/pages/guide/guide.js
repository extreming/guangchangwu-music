var library = require('../../utils/library.js')
var bridge = require('../../utils/bridge.js')

function stepsFor(phone) {
  var common = [
    { n: '1', text: '点绿色按钮「发给文件传输助手」。', img: '/images/guide/step1.png' },
    { n: '2', text: '在名单里找到「文件传输助手」，点它。', img: '/images/guide/step2.png' },
    { n: '3', text: '打开那个聊天，点一下刚发出的音乐文件。', img: '/images/guide/step3.png' }
  ]
  if (phone === 'ios') {
    common.push({
      n: '4',
      text: '点「用其他应用打开」，再点「存储到文件」。这样就能在苹果的「文件」App里找到它。',
      img: '/images/guide/ios4.png'
    })
  } else {
    common.push({
      n: '4',
      text: '点「保存」，或者点「用其他应用打开」。音乐就留在手机里了。',
      img: '/images/guide/android4.png'
    })
  }
  return common
}

Page({
  data: {
    phone: 'android',
    phoneNote: '',
    steps: [],
    canShare: false,
    link: '',
    statusText: '',
    safeBottom: 0,
    track: null
  },

  onLoad: function () {
    var sys = wx.getSystemInfoSync()
    var phone = sys.platform === 'ios' ? 'ios' : 'android'
    var track = library.get(bridge.getTarget())
    this.setData({
      phone: phone,
      phoneNote: phone === 'ios'
        ? '苹果手机不能一键存进文件夹。按下面四步来，做一次就会了。'
        : '安卓手机按下面四步，可以把音乐另外存进手机。',
      steps: stepsFor(phone),
      track: track,
      canShare: !!(track && track.filePath),
      link: track && track.remoteUrl ? track.remoteUrl : ''
    })
  },

  onShow: function () {
    var app = getApp()
    this.setData({ safeBottom: app.globalData.safeBottom || 0 })
  },

  setPhone: function (e) {
    var phone = e.currentTarget.dataset.phone
    this.setData({
      phone: phone,
      phoneNote: phone === 'ios'
        ? '苹果手机不能一键存进文件夹。按下面四步来，做一次就会了。'
        : '安卓手机按下面四步，可以把音乐另外存进手机。',
      steps: stepsFor(phone)
    })
  },

  onShare: function () {
    var track = this.data.track
    if (!track) return
    var that = this
    if (!wx.shareFileMessage) {
      this.onCopy()
      this.setData({ statusText: '这个微信不能直接发文件。请用下面的复制链接。' })
      return
    }
    wx.shareFileMessage({
      filePath: track.filePath,
      fileName: track.fileName || '舞曲.mp3',
      success: function () {
        that.setData({ statusText: '请点「文件传输助手」，发出去后再按第3步点开文件。' })
      },
      fail: function (err) {
        var msg = (err && err.errMsg) || ''
        if (msg.indexOf('cancel') >= 0) return
        that.setData({ statusText: '没能发出去。请用下面的「复制下载链接」。' })
      }
    })
  },

  onCopy: function () {
    var that = this
    if (!this.data.link) {
      this.setData({ statusText: '链接已经过期。请重新提取一次，马上再来复制。' })
      return
    }
    wx.setClipboardData({
      data: this.data.link,
      success: function () {
        that.setData({ statusText: '链接已复制。请马上打开浏览器，在地址栏长按粘贴。这个链接过几小时会失效。' })
      }
    })
  },

  goBack: function () {
    wx.navigateBack({
      delta: 1,
      fail: function () {
        wx.reLaunch({ url: '/pages/index/index' })
      }
    })
  }
})
