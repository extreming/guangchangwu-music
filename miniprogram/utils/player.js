var bgm = null
var inner = null
var inited = false
var listeners = []
var lastEmit = 0
var timer = null

var state = {
  trackId: '',
  title: '',
  src: '',
  playing: false,
  loop: true,
  current: 0,
  duration: 0,
  hint: '点大大的「播放」。音量按手机侧面的按键。',
  waiting: false,
  wantPlay: false,
  mode: ''
}

function readLoop() {
  var value
  try {
    value = wx.getStorageSync('gcw_loop')
  } catch (e) {
    return true
  }
  if (value === '' || value === undefined || value === null) return true
  return !!value
}

function snapshot() {
  return {
    trackId: state.trackId,
    title: state.title,
    playing: state.playing,
    loop: state.loop,
    current: state.current,
    duration: state.duration,
    hint: state.hint,
    waiting: state.waiting,
    mode: state.mode
  }
}

function emitNow() {
  lastEmit = Date.now()
  var snap = snapshot()
  for (var i = 0; i < listeners.length; i++) {
    try {
      listeners[i](snap)
    } catch (e) {}
  }
}

function emit(force) {
  var now = Date.now()
  if (!force && now - lastEmit < 400) {
    if (!timer) {
      timer = setTimeout(function () {
        timer = null
        emitNow()
      }, 400)
    }
    return
  }
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  emitNow()
}

function stopInner() {
  if (!inner) return
  try {
    inner.stop()
  } catch (e) {}
}

function getInner() {
  if (inner) return inner
  inner = wx.createInnerAudioContext()
  inner.obeyMuteSwitch = false
  inner.autoplay = false
  inner.onPlay(function () {
    if (state.mode !== 'inner') return
    state.playing = true
    state.waiting = false
    state.hint = '播放时请让屏幕亮着。音量按手机侧面的按键。'
    emit(true)
  })
  inner.onPause(function () {
    if (state.mode !== 'inner') return
    state.playing = false
    state.waiting = false
    emit(true)
  })
  inner.onStop(function () {
    if (state.mode !== 'inner') return
    state.playing = false
    state.waiting = false
    emit(true)
  })
  inner.onEnded(function () {
    if (state.mode !== 'inner') return
    if (!state.loop) {
      state.playing = false
      state.wantPlay = false
      emit(true)
    }
  })
  inner.onTimeUpdate(function () {
    if (state.mode !== 'inner') return
    state.current = inner.currentTime || 0
    if (inner.duration) state.duration = inner.duration
    state.playing = true
    emit(false)
  })
  inner.onWaiting(function () {
    if (state.mode !== 'inner') return
    state.waiting = true
    emit(false)
  })
  inner.onCanplay(function () {
    if (state.mode === 'inner' && state.wantPlay && !state.playing) {
      inner.play()
    }
  })
  inner.onError(function () {
    if (state.mode !== 'inner') return
    state.playing = false
    state.waiting = false
    state.wantPlay = false
    state.hint = '播放失败。请返回，重新提取一次。'
    emit(true)
  })
  return inner
}

function startInner() {
  var audio = getInner()
  state.mode = 'inner'
  state.waiting = true
  state.wantPlay = true
  audio.loop = !!state.loop
  try {
    audio.stop()
  } catch (e) {}
  audio.src = state.src
  audio.play()
  emit(true)
}

function fallbackInner() {
  state.mode = 'inner'
  state.hint = '播放时请让屏幕亮着。音量按手机侧面的按键。'
  try {
    if (bgm) bgm.stop()
  } catch (e) {}
  startInner()
}

function startBgm() {
  stopInner()
  state.mode = 'bgm'
  state.waiting = true
  state.wantPlay = true
  if (!bgm) {
    fallbackInner()
    return
  }
  bgm.title = state.title || '广场舞音乐'
  bgm.singer = '广场舞'
  bgm.epname = '我的音乐'
  bgm.src = state.src
}

function bindBgm() {
  if (!wx.getBackgroundAudioManager) return
  try {
    bgm = wx.getBackgroundAudioManager()
  } catch (e) {
    bgm = null
    return
  }
  bgm.onPlay(function () {
    if (state.mode !== 'bgm') return
    state.playing = true
    state.waiting = false
    state.hint = '可以锁屏，音乐会接着放。音量按手机侧面的按键。'
    emit(true)
  })
  bgm.onPause(function () {
    if (state.mode !== 'bgm') return
    state.playing = false
    state.waiting = false
    emit(true)
  })
  bgm.onStop(function () {
    if (state.mode !== 'bgm') return
    state.playing = false
    state.waiting = false
    emit(true)
  })
  bgm.onEnded(function () {
    if (state.mode !== 'bgm') return
    if (state.loop && state.src) {
      bgm.title = state.title || '广场舞音乐'
      bgm.singer = '广场舞'
      bgm.epname = '我的音乐'
      bgm.src = state.src
      return
    }
    state.playing = false
    state.wantPlay = false
    emit(true)
  })
  bgm.onTimeUpdate(function () {
    if (state.mode !== 'bgm') return
    state.current = bgm.currentTime || 0
    if (bgm.duration) state.duration = bgm.duration
    emit(false)
  })
  bgm.onWaiting(function () {
    if (state.mode !== 'bgm') return
    state.waiting = true
    emit(false)
  })
  bgm.onError(function () {
    if (state.mode !== 'bgm') return
    fallbackInner()
  })
}

function init() {
  if (inited) return
  inited = true
  state.loop = readLoop()
  bindBgm()
}

function playTrack(track) {
  init()
  if (!track || !track.filePath) return
  state.trackId = track.id
  state.title = track.title || '广场舞音乐'
  state.src = track.filePath
  state.current = 0
  state.duration = track.duration || 0
  state.hint = '正在打开音乐…'
  emit(true)
  startBgm()
}

function pause() {
  state.wantPlay = false
  state.waiting = false
  if (state.mode === 'inner' && inner) {
    try {
      inner.pause()
    } catch (e) {}
  } else if (bgm) {
    try {
      bgm.pause()
    } catch (e) {}
  }
  state.playing = false
  emit(true)
}

function resume() {
  state.wantPlay = true
  state.waiting = true
  if (state.mode === 'inner' && inner) {
    inner.play()
    return
  }
  if (state.mode === 'bgm' && bgm && state.src) {
    try {
      bgm.play()
    } catch (e) {
      startBgm()
    }
    return
  }
  playTrack({ id: state.trackId, title: state.title, filePath: state.src, duration: state.duration })
}

function toggle(track) {
  init()
  if (!track) return
  if (state.trackId === track.id && state.playing) {
    pause()
    return
  }
  if (state.trackId === track.id && state.src) {
    resume()
    return
  }
  playTrack(track)
}

function setLoop(on) {
  init()
  state.loop = !!on
  try {
    wx.setStorageSync('gcw_loop', state.loop)
  } catch (e) {}
  if (inner && state.mode === 'inner') {
    inner.loop = state.loop
  }
  emit(true)
}

function stopIf(id) {
  if (state.trackId !== id) return
  state.wantPlay = false
  stopInner()
  try {
    if (bgm) bgm.stop()
  } catch (e) {}
  state.trackId = ''
  state.src = ''
  state.playing = false
  state.current = 0
  state.waiting = false
  emit(true)
}

function subscribe(fn) {
  listeners.push(fn)
  fn(snapshot())
  return function () {
    var index = listeners.indexOf(fn)
    if (index >= 0) listeners.splice(index, 1)
  }
}

function getState() {
  return snapshot()
}

module.exports = {
  init: init,
  playTrack: playTrack,
  toggle: toggle,
  setLoop: setLoop,
  stopIf: stopIf,
  subscribe: subscribe,
  getState: getState
}
