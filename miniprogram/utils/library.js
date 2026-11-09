var format = require('./format.js')

var STORAGE_KEY = 'gcw_music_v1'
var MAX_SONGS = 40

function musicDir() {
  return wx.env.USER_DATA_PATH + '/music'
}

function pathFor(id) {
  return musicDir() + '/' + id + '.mp3'
}

function ensureDir() {
  var fs = wx.getFileSystemManager()
  var dir = musicDir()
  try {
    fs.accessSync(dir)
  } catch (e) {
    try {
      fs.mkdirSync(dir, true)
    } catch (err) {}
  }
  return dir
}

function readAll() {
  var raw
  try {
    raw = wx.getStorageSync(STORAGE_KEY)
  } catch (e) {
    raw = []
  }
  if (!raw || !raw.length) return []
  var out = []
  for (var i = 0; i < raw.length; i++) {
    var item = raw[i]
    if (!item || !item.id) continue
    item.filePath = pathFor(item.id)
    out.push(item)
  }
  return out
}

function writeAll(list) {
  wx.setStorageSync(STORAGE_KEY, list)
}

function trim(list) {
  var fs = wx.getFileSystemManager()
  while (list.length > MAX_SONGS) {
    var old = list.pop()
    if (old && old.id) {
      try {
        fs.unlinkSync(pathFor(old.id))
      } catch (e) {}
    }
  }
  return list
}

function saveFromTemp(tempFilePath, meta) {
  var fs = wx.getFileSystemManager()
  ensureDir()
  var id = meta.id
  if (!id) {
    throw new Error('没能存进「我的音乐」。请再试一次。')
  }
  var dest = pathFor(id)
  try {
    fs.copyFileSync(tempFilePath, dest)
  } catch (e) {
    try {
      fs.unlinkSync(dest)
    } catch (e2) {}
    try {
      fs.copyFileSync(tempFilePath, dest)
    } catch (e3) {
      throw new Error('没能存进「我的音乐」。可能是空间满了，请先删掉几首旧的。')
    }
  }
  var track = {
    id: id,
    title: meta.title || '未命名音乐',
    fileName: format.shareName(meta.filename, meta.title),
    platform: meta.platform || '',
    platformLabel: meta.platform_label || '',
    duration: meta.duration || 0,
    createdAt: Date.now(),
    remoteUrl: meta.audio_url || ''
  }
  var list = readAll()
  var kept = []
  for (var i = 0; i < list.length; i++) {
    if (list[i].id !== id) kept.push(list[i])
  }
  kept.unshift(track)
  writeAll(trim(kept))
  track.filePath = dest
  return track
}

function get(id) {
  var list = readAll()
  for (var i = 0; i < list.length; i++) {
    if (list[i].id === id) return list[i]
  }
  return null
}

function remove(id) {
  var fs = wx.getFileSystemManager()
  var list = readAll()
  var next = []
  for (var i = 0; i < list.length; i++) {
    if (list[i].id === id) {
      try {
        fs.unlinkSync(pathFor(id))
      } catch (e) {}
    } else {
      next.push(list[i])
    }
  }
  writeAll(next)
}

function fileExists(filePath) {
  try {
    wx.getFileSystemManager().accessSync(filePath)
    return true
  } catch (e) {
    return false
  }
}

function decorate(list, playingId) {
  var rows = []
  for (var i = 0; i < list.length; i++) {
    var item = list[i]
    var bits = []
    var durationText = format.formatDuration(item.duration)
    if (durationText) bits.push(durationText)
    if (item.platformLabel) bits.push('来自' + item.platformLabel)
    bits.push(format.formatWhen(item.createdAt))
    rows.push({
      id: item.id,
      title: item.title,
      meta: bits.join(' · '),
      playing: item.id === playingId
    })
  }
  return rows
}

module.exports = {
  readAll: readAll,
  saveFromTemp: saveFromTemp,
  get: get,
  remove: remove,
  fileExists: fileExists,
  decorate: decorate
}
