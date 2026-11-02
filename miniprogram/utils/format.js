function pad(n) {
  return n < 10 ? '0' + n : '' + n
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function formatDuration(sec) {
  sec = Math.round(Number(sec) || 0)
  if (sec <= 0) return ''
  var m = Math.floor(sec / 60)
  var s = sec % 60
  if (m <= 0) return s + '秒'
  if (s === 0) return m + '分钟'
  return m + '分' + s + '秒'
}

function formatWhen(ts) {
  if (!ts) return ''
  var d = new Date(ts)
  var now = new Date()
  var hm = pad(d.getHours()) + ':' + pad(d.getMinutes())
  if (sameDay(d, now)) return '今天 ' + hm
  var yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  if (sameDay(d, yesterday)) return '昨天 ' + hm
  return (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + hm
}

function shareName(name, title) {
  var raw = name || title || '未命名音乐'
  raw = String(raw).replace(/[\\/:*?"<>|\r\n]/g, '').trim()
  if (!raw) raw = '未命名音乐'
  if (raw.length > 60) raw = raw.slice(0, 60)
  if (raw.toLowerCase().lastIndexOf('.mp3') !== raw.length - 4) {
    raw = raw + '.mp3'
  }
  return raw
}

module.exports = {
  formatDuration: formatDuration,
  formatWhen: formatWhen,
  shareName: shareName
}
