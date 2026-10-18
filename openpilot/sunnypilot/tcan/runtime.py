"""Offline Auto Blinker request scheduler, with no transport or CAN payloads.

Policy subset from T2CAN e63b678df385748ffe379ebebdd98b73a361c3d8
(auto_blinker_pure.h and vehicle_logic.h). Authority expiry is stricter here.
"""


def alc_allows(direction, alc):
  return (direction == 1 and alc in (6, 8)) or (direction == 2 and alc in (7, 8))


def session_decision(gate, pending, current, recent, elapsed, allowed, due):
  if not gate or not pending or not recent or (current and current != pending):
    return 'cancel'
  if not elapsed or not due:
    return 'wait'
  return 'fire' if allowed else 'retry'


class AutoBlinkerRuntime:
  def __init__(self, delay_ms=2000, stabilization_ms=10000, pause_ms=20000):
    if (type(delay_ms) is not int or not 0 <= delay_ms <= 20000 or
        type(stabilization_ms) is not int or not 1000 <= stabilization_ms <= 20000 or
        type(pause_ms) is not int or not 10000 <= pause_ms <= 100000):
      raise ValueError('invalid scheduler durations')
    self.delay_ms = delay_ms
    self.stabilization_ms = stabilization_ms
    self.pause_ms = pause_ms
    self.last_ms = None
    self._reset('disabled')

  def _reset(self, reason):
    self.lease_until = None
    self.ready_at = None
    self.exit_at = None
    self.pause_until = None
    self.last_direction = 0
    self.request_seen = None
    self.state = {'phase': 'inactive', 'pending': 0, 'fire_at_ms': None,
                  'retry_at_ms': None, 'retry_count': 0, 'reason': reason}

  def _clear_request(self):
    self.last_direction = 0
    self.request_seen = None
    self.state.update(pending=0, fire_at_ms=None, retry_at_ms=None)

  def step(self, now_ms, *, authority_ms, sp_onroad, state_ms, ap_state, alc_state,
           request_ms, behavior, enabled=False, cancel=False):
    times = (now_ms, authority_ms, state_ms, request_ms)
    if (type(now_ms) is not int or any(t is not None and (type(t) is not int or t < 0) for t in times) or
        any(type(b) is not bool for b in (sp_onroad, enabled, cancel)) or
        type(ap_state) is not int or not 0 <= ap_state <= 15 or
        type(alc_state) is not int or not 0 <= alc_state <= 31 or
        type(behavior) is not int or not 0 <= behavior <= 3):
      self._reset('invalid_input')
      raise ValueError('invalid offline snapshot')
    backwards = self.last_ms is not None and now_ms < self.last_ms
    self.last_ms = now_ms
    if (backwards or not enabled or sp_onroad or authority_ms is None or state_ms is None or
        not 0 <= now_ms - authority_ms <= 250 or not 0 <= now_ms - state_ms <= 1000 or
        (request_ms is not None and request_ms > now_ms)):
      self._reset('authority_revoked')
      return []

    if self.lease_until is not None and now_ms > self.lease_until:
      self._reset('lease_expired_between_steps')
    self.lease_until = authority_ms + 250

    if ap_state == 5:
      if self.ready_at is None or (self.exit_at is not None and now_ms >= self.exit_at):
        self.ready_at = now_ms + self.stabilization_ms
      self.exit_at = None
    elif self.ready_at is not None:
      if self.exit_at is None:
        self.exit_at = now_ms + 2000
      if now_ms >= self.exit_at:
        self.ready_at = None
        self.exit_at = None
    if self.ready_at is None or self.exit_at is not None or now_ms < self.ready_at:
      self._clear_request()
      self.state.update(phase='exit_wait' if self.exit_at is not None else 'stabilizing' if self.ready_at is not None else 'inactive',
                        reason='noa_not_ready')
      return []

    if self.pause_until is not None and now_ms >= self.pause_until:
      self.pause_until = None
    if cancel:
      self.pause_until = None if self.pause_until is not None else now_ms + self.pause_ms
      self._clear_request()
    if self.pause_until is not None:
      self.state.update(phase='paused', reason='manual_cancel')
      return []

    current = {2: 1, 3: 2}.get(behavior, 0) if request_ms is not None and now_ms - request_ms <= 2000 else 0
    if current:
      if current != self.last_direction:
        self.state.update(pending=current, fire_at_ms=now_ms + self.delay_ms, retry_at_ms=now_ms + self.delay_ms)
      self.last_direction = current
      self.request_seen = request_ms
      if self.state['pending'] and now_ms >= self.state['fire_at_ms'] and alc_allows(current, alc_state):
        self.state['retry_at_ms'] = now_ms
    recent = self.request_seen is not None and now_ms - self.request_seen <= 2000
    if not recent:
      self._clear_request()
      self.state.update(phase='ready', reason='request_expired')
      return []
    if not self.state['pending']:
      self.state.update(phase='latched', reason='already_proposed')
      return []
    pending = self.state['pending']
    decision = session_decision(True, pending, current, recent, now_ms >= self.state['fire_at_ms'],
                                alc_allows(pending, alc_state), now_ms >= self.state['retry_at_ms'])
    self.state.update(phase='pending', reason=decision)
    if decision == 'retry':
      self.state['retry_at_ms'] = now_ms + 250
      self.state['retry_count'] += 1
    elif decision == 'fire':
      self.state.update(pending=0, fire_at_ms=None, retry_at_ms=None, phase='latched')
      return [{'kind': 'blinker_request', 'direction': 'left' if pending == 1 else 'right',
               'at_ms': now_ms, 'shadow_only': True}]
    return []
