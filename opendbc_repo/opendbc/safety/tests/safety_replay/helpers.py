from opendbc.car.structs import CarParams
from opendbc.safety.tests.libsafety import libsafety_py


def to_signed(d, bits):
  ret = d
  if d >= (1 << (bits - 1)):
    ret = d - (1 << bits)
  return ret


def is_steering_msg(mode, param, addr):
  return mode == CarParams.SafetyModel.tesla and addr == 0x488


def get_steer_value(mode, param, msg):
  # TODO: use CANParser
  torque, angle = 0, 0
  if mode == CarParams.SafetyModel.tesla:
    angle = (((msg.data[0] & 0x7F) << 8) | (msg.data[1])) - 16384  # ceil(1638.35/0.1)
  return torque, angle


def package_can_msg(msg):
  return libsafety_py.make_CANPacket(msg.address, msg.src % 4, msg.dat)


def init_segment(safety, msgs, mode, param):
  sendcan = (msg for msg in msgs if msg.which() == 'sendcan')
  steering_msgs = (can for msg in sendcan for can in msg.sendcan if is_steering_msg(mode, param, can.address))

  msg = next(steering_msgs, None)
  if msg is None:
    print("no steering msgs found!")
    return

  msg = package_can_msg(msg)
  torque, angle = get_steer_value(mode, param, msg)
  if torque != 0:
    safety.set_controls_allowed(1)
    safety.set_controls_allowed_lateral(1)
    safety.set_desired_torque_last(torque)
    safety.set_rt_torque_last(torque)
    safety.set_torque_meas(torque, torque)
    safety.set_torque_driver(torque, torque)
  elif angle != 0:
    safety.set_controls_allowed(1)
    safety.set_controls_allowed_lateral(1)
    safety.set_desired_angle_last(angle)
    safety.set_angle_meas(angle, angle)
    safety.set_desired_curvature_last(angle)
    safety.set_curvature_meas(angle, angle)
  assert safety.safety_tx_hook(msg), "failed to initialize safety for segment"
