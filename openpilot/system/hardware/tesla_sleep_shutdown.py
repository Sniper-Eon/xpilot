"""Opt-in wait after a parked Tesla goes to sleep.

Ignition here is the harness line or Tesla VCFRONT vehiclePowerState DRIVE.
Leaving DRIVE only means the car is parked. The body controller keeps talking
until the car actually sleeps, which is the vehicle bus going quiet.

The device's own 12V draw can hold that bus awake forever, so ignition-off
also has a bounded delay. Both paths stay closed while the toggle is off,
while ignition is on, while the driver is on the brake or out of Park, while
openpilot is onroad, while the harness is unplugged, or while no panda is
alive. A boot into an already quiet bus does not arm: the car has to have
been seen awake first.

sudo poweroff stops the SOM. The SOM is then blind to the brake pedal and to
the gear lever. The panda on a comma three stays up and bootkicks the SOM
only on a rising ignition edge (harness line, or vehiclePowerState DRIVE).
Brake-in-Park is not that edge, and comma three does not use the comma four
CAN stop-mode wake. If Tesla sleep leaves 12V present, a poweroff stays off
until the power button or a real power cycle. This policy poweroffs only
after a supply that was already present falls below POWER_CUT_MV, so the
next 12V restore cold-boots the PMIC. Otherwise it holds in low power and
the screen wakes on the brake or on a gear other than Park.
"""
import threading

CAN_SILENCE_S = 120.0
IGNITION_OFF_DELAY_S = 15 * 60.0

# Harness millivolts. A live Tesla LV pack (12V lead or 16V lithium) sits
# above POWER_PRESENT_MV. POWER_CUT_MV is the supply falling out, not a sag.
POWER_PRESENT_MV = 11000.0
POWER_CUT_MV = 8000.0
POWER_CUT_SAMPLES = 3

# DI_systemStatus (280) and ESP_status (325) on the Tesla party bus.
DI_SYSTEM_STATUS = 0x118
ESP_STATUS = 0x145
SIGNAL_TTL_S = 1.0
SCREEN_WAKE_S = 30.0
WAKE_BUSES = frozenset({0, 2})
# DI_gear: R=2, N=3, D=4. Park is 1. 0 and 7 are invalid / SNA.
GEAR_NOT_PARK = frozenset({2, 3, 4})
DI_BRAKE_ON = 1
ESP_BRAKE_APPLYING = 2


def panda_can_rx(panda_states) -> int | None:
  """Sum receive counters on every panda bus. None when no counter exists."""
  total = 0
  found = False
  for panda in panda_states:
    for bus in ("canState0", "canState1", "canState2"):
      state = getattr(panda, bus, None)
      count = None if state is None else getattr(state, "totalRxCnt", None)
      if count is None:
        continue
      total += int(count)
      found = True
  return total if found else None


def le_bits(data: bytes, start: int, length: int) -> int | None:
  """Intel (@1+) bitfield. None when the frame is shorter than the field."""
  if length <= 0 or length > 8 or start < 0 or (start + length) > len(data) * 8:
    return None
  raw = int.from_bytes(data[:8], "little")
  return (raw >> start) & ((1 << length) - 1)


class TeslaSleepShutdown:
  def __init__(self) -> None:
    self.seen_awake = False
    self.holding = False
    self._last_rx: int | None = None
    self._silent_since: float | None = None
    self._ignition_off_since: float | None = None
    self._traffic_since_off = False
    self._seen_present = False
    self._cut_samples = 0
    self._lock = threading.Lock()
    self._counters: dict[str, int] = {}
    self._brake = False
    self._gear: int | None = None
    self._signal_at: float | None = None
    self._screen_until: float | None = None

  def observe_frame(self, address: int, bus: int, data: bytes, now: float) -> None:
    """Fold one CAN frame into the brake / gear wake. Safe from another thread."""
    if bus not in WAKE_BUSES or not isinstance(data, (bytes, bytearray)):
      return
    data = bytes(data)
    with self._lock:
      if address == DI_SYSTEM_STATUS and len(data) >= 8:
        if not self._counter_ok("di", le_bits(data, 8, 4)):
          return
        self._gear = le_bits(data, 21, 3)
        self._brake = le_bits(data, 19, 2) == DI_BRAKE_ON
        self._signal_at = now
      elif address == ESP_STATUS and len(data) >= 8:
        if not self._counter_ok("esp", le_bits(data, 8, 4)):
          return
        if le_bits(data, 29, 2) == ESP_BRAKE_APPLYING:
          self._brake = True
          self._signal_at = now

  def _counter_ok(self, key: str, counter: int | None) -> bool:
    if counter is None:
      return False
    prev = self._counters.get(key, -1)
    self._counters[key] = counter
    return prev >= 0 and counter == (prev + 1) % 16

  def driver_present(self, now: float) -> bool:
    """True when a fresh frame shows the brake or a gear other than Park."""
    with self._lock:
      if self._signal_at is None or (now - self._signal_at) > SIGNAL_TTL_S:
        self._brake = False
        self._gear = None
        self._signal_at = None
        return False
      return self._brake or self._gear in GEAR_NOT_PARK

  def note_screen(self, present: bool, now: float) -> bool:
    """Keep the screen awake briefly after the pedal or the lever lets go."""
    if present:
      self._screen_until = now + SCREEN_WAKE_S
    return self._screen_until is not None and now < self._screen_until

  def disarm(self) -> None:
    """Toggle off: drop the hold and do not keep a stale screen wake."""
    self.holding = False
    self._screen_until = None

  def note_voltage(self, voltage_mv: float | None) -> None:
    if voltage_mv is None or voltage_mv <= 0:
      self._cut_samples = 0
      return
    if voltage_mv >= POWER_PRESENT_MV:
      self._seen_present = True
      self._cut_samples = 0
    elif self._seen_present and voltage_mv < POWER_CUT_MV:
      self._cut_samples += 1
    else:
      self._cut_samples = 0

  def power_is_dropping(self) -> bool:
    return self._cut_samples >= POWER_CUT_SAMPLES

  def sleep_action(self, reason: str | None, voltage_mv: float | None) -> str | None:
    """'hold', 'poweroff', or None.

    poweroff only after a live supply has fallen through POWER_CUT_MV.
    A missing or never-live reading holds, because a poweroff would then
    wait for a power button.
    """
    self.note_voltage(voltage_mv)
    dropping = self.power_is_dropping()
    if reason is None and not (self.holding and dropping):
      return None
    if dropping:
      self.holding = False
      return "poweroff"
    self.holding = True
    return "hold"

  def update(self, *, enabled: bool, ignition: bool, started: bool, in_car: bool,
             panda_alive: bool, can_rx: int | None, now: float,
             driver_present: bool = False) -> str | None:
    """Return 'can-silence' or 'ignition-off-delay' when sleep should arm."""
    rx_changed = False
    if panda_alive and can_rx is not None:
      if self._last_rx is not None and can_rx != self._last_rx:
        rx_changed = True
        self.seen_awake = True
      self._last_rx = can_rx
    else:
      self._last_rx = None

    # Onroad, DRIVE, brake, or a gear other than Park: never arm.
    if ignition or started or driver_present:
      self.seen_awake = True
      self._clear_park()
      self.holding = False
      return None

    if not (enabled and in_car and panda_alive and self.seen_awake):
      self._clear_park()
      self.holding = False
      return None

    if self._ignition_off_since is None:
      self._ignition_off_since = now
    if rx_changed:
      self._traffic_since_off = True

    # Silence counts only after a frame arrived while already parked. A bus that
    # dies in the same moment as ignition must use the longer delay instead.
    if not self._traffic_since_off or can_rx is None or rx_changed:
      self._silent_since = None
    elif self._silent_since is None:
      self._silent_since = now
    elif now - self._silent_since >= CAN_SILENCE_S:
      return "can-silence"

    if now - self._ignition_off_since >= IGNITION_OFF_DELAY_S:
      return "ignition-off-delay"
    return None

  def _clear_park(self) -> None:
    self._ignition_off_since = None
    self._silent_since = None
    self._traffic_since_off = False
