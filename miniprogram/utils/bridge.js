var targetId = ''

function setTarget(id) {
  targetId = id || ''
}

function getTarget() {
  return targetId
}

module.exports = {
  setTarget: setTarget,
  getTarget: getTarget
}
