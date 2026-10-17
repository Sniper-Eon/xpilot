"""Offline intermediate transforms; no transport or transmit-ready CAN output.

Ported subset of T2CAN e63b678df385748ffe379ebebdd98b73a361c3d8:
r79_fixed_policy_pure.h, isa_suppression_pure.h, country_override_pure.h.
The caller's A/B mapping describes replay data, never verified vehicle wiring.
"""


class ShadowEngine:
  def __init__(self, profile=None, bus_map=None, features=()):
    if profile not in (None, "yl", "standard_body", "standard_party"):
      raise ValueError("unknown offline profile")
    if bus_map is not None and (set(bus_map) != {"A", "B"} or
                               any(type(bus) is not int or not 0 <= bus <= 255 for bus in bus_map.values()) or
                               bus_map["A"] == bus_map["B"]):
      raise ValueError("offline mapping requires two distinct bus numbers")
    if set(features) - {"r79", "isa", "country_us"}:
      raise ValueError("unknown shadow feature")
    self.profile = profile
    self.bus_map = dict(bus_map) if bus_map is not None else None
    self.features = frozenset(features)
    self.ap_received_ns = None
    self.last_ns = None

  def observe(self, bus, address, data, now_ns, *, received_ns=None, sp_onroad=False):
    received_ns = now_ns if received_ns is None else received_ns
    if (type(bus) is not int or type(address) is not int or not 0 <= address <= 0x7FF or
        not isinstance(data, bytes) or type(now_ns) is not int or type(received_ns) is not int or
        type(sp_onroad) is not bool or now_ns < 0 or received_ns < 0):
      raise ValueError("invalid offline CAN observation")
    backwards = self.last_ns is not None and now_ns < self.last_ns
    self.last_ns = now_ns
    if sp_onroad or backwards:
      self.ap_received_ns = None
      return []
    if self.profile is None or self.bus_map is None or bus not in self.bus_map.values():
      return []
    if len(data) != 8 or not 0 <= now_ns - received_ns <= 250_000_000:
      return []
    ap_bus = self.bus_map["A" if self.profile == "yl" else "B"]
    if address == 0x399 and bus == ap_bus:
      self.ap_received_ns = received_ns if 3 <= data[0] & 15 <= 6 else None
    if self.ap_received_ns is None or not 0 <= now_ns - self.ap_received_ns <= 1_000_000_000:
      return []
    out = bytearray(data)
    feature = None
    if "r79" in self.features and bus == self.bus_map["B"] and address == 0x3FD and data[0] & 7 == 1:
      out[2] &= ~8
      out[5] |= 128
      feature = "r79"
    elif "isa" in self.features and bus == ap_bus and address == 0x399:
      out[1] |= 32
      feature = "isa"
    elif ("country_us" in self.features and address == 0x238 and
          (bus == self.bus_map["B"] or self.profile == "standard_body")):
      source = data[2] | ((data[3] & 3) << 8)
      if data[7] == (0x38 + 2 + sum(data[:7])) & 255 and 1 <= source <= 999 and source != 840:
        out[2] = 840 & 255
        out[3] = (out[3] & 252) | (840 >> 8)
        out[6] = (out[6] & 15) | ((((out[6] >> 4) + 1) & 15) << 4)
        out[7] = (0x38 + 2 + sum(out[:7])) & 255
        feature = "country_us"
    if feature is None or out == data:
      return []
    return [{"feature": feature, "bus": bus, "address": address, "data_hex": out.hex(), "shadow_only": True}]
