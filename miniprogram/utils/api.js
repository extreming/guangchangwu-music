var config = require('../config.js')

function messageFromFail(err) {
  var msg = (err && err.errMsg) || ''
  if (msg.indexOf('timeout') >= 0) {
    return '等太久了。请检查网络，或换一首短一点的。'
  }
  return '连不上服务器。请让家人检查网络，并确认服务器已经打开。'
}

function requestHeader() {
  var header = { 'content-type': 'application/json' }
  if (config.apiToken) header['X-Api-Token'] = config.apiToken
  return header
}

function downloadHeader() {
  var header = {}
  if (config.apiToken) header['X-Api-Token'] = config.apiToken
  return header
}

function extract(text) {
  return new Promise(function (resolve, reject) {
    wx.request({
      url: config.apiBase + '/api/extract',
      method: 'POST',
      timeout: 60000,
      data: { text: text },
      header: requestHeader(),
      success: function (res) {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.audio_url) {
          resolve(res.data)
          return
        }
        var msg = (res.data && res.data.error) || '提取失败，请稍后再试。'
        reject(new Error(msg))
      },
      fail: function (err) {
        reject(new Error(messageFromFail(err)))
      }
    })
  })
}

function download(url) {
  return new Promise(function (resolve, reject) {
    wx.downloadFile({
      url: url,
      timeout: 60000,
      header: downloadHeader(),
      success: function (res) {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          reject(new Error('音乐下载失败。请检查网络后再试一次。'))
          return
        }
        wx.getFileInfo({
          filePath: res.tempFilePath,
          success: function (info) {
            if (!info.size || info.size < 200) {
              reject(new Error('下载到的音乐是空的。请换一个链接。'))
              return
            }
            resolve(res.tempFilePath)
          },
          fail: function () {
            resolve(res.tempFilePath)
          }
        })
      },
      fail: function (err) {
        reject(new Error(messageFromFail(err)))
      }
    })
  })
}

function hasUrl(text) {
  return /https?:\/\/\S+/i.test(text || '')
}

module.exports = {
  extract: extract,
  download: download,
  hasUrl: hasUrl,
  apiBase: config.apiBase
}
