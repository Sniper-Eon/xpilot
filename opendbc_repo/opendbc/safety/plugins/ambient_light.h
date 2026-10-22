#pragma once

// xpilot plugin "ambient_light": blindspot ambient lighting on 0x679 (vehicle bus 1), cloned from a fresh
// car frame, red palette only, rate and session limited. Active in the Tesla mode, and in nooutput with
// param 1 (offroad light test). Python side: openpilot/tesla/plugins/ambient_light/.

static uint8_t ambient_template[7] = {0U};
static bool ambient_template_valid = false;
static uint32_t ambient_template_ts = 0U;
static bool ambient_tx_valid = false;
static uint32_t ambient_tx_ts = 0U;
static uint32_t ambient_session_ts = 0U;
static uint8_t ambient_session_count = 0U;

static bool ambient_offroad_test(void) {
  return (current_safety_mode == SAFETY_NOOUTPUT) && (current_safety_param == 1U);
}

static bool ambient_active(void) {
  return ((current_safety_mode == SAFETY_TESLA) && tesla_has_vehicle_bus) || ambient_offroad_test();
}

static void ambient_rx(const CANPacket_t *msg) {
  if ((msg->bus == 1U) && (msg->addr == 0x679U) && (GET_LEN(msg) == 7U)) {
    for (uint8_t i = 0U; i < 7U; i++) {
      ambient_template[i] = msg->data[i];
    }
    ambient_template_ts = microsecond_timer_get();
    ambient_template_valid = true;
  }
}

static bool ambient_tx(const CANPacket_t *msg) {
  const uint32_t now = microsecond_timer_get();
  const bool offroad = ambient_offroad_test();
  const bool fresh = ambient_template_valid && (safety_get_ts_elapsed(now, ambient_template_ts) <= 1000000U);
  const uint8_t zone = msg->data[5] & 0xF8U;
  const bool side = (msg->data[6] & 1U) == 1U;
  const bool target = ((zone == 0xA8U) && !side) || ((zone == 0x50U) && side) || (!offroad && (zone == 0xF8U) && side);
  const uint8_t brightness = msg->data[4] & 0x7FU;
  const bool red = (msg->data[1] == 255U) && (msg->data[2] == 0U) && (msg->data[3] == 0U) &&
                   (offroad ? (brightness == 100U) : (brightness <= 100U));
  const bool matches_template = (msg->data[0] == ((ambient_template[0] & 1U) | 2U)) &&
    ((msg->data[4] & 0x80U) == (ambient_template[4] & 0x80U)) &&
    ((msg->data[5] & 7U) == (ambient_template[5] & 6U)) &&
    ((msg->data[6] & 0xFEU) == (ambient_template[6] & 0xFEU));
  const bool new_session = !ambient_tx_valid || (safety_get_ts_elapsed(now, ambient_tx_ts) >= 1000000U);
  const bool rate = !ambient_tx_valid || (safety_get_ts_elapsed(now, ambient_tx_ts) >= 80000U);
  // Host sends at 10 Hz: 150 frames / 15 s onroad, 30 frames / 3 s for the offroad test.
  const uint32_t session_us = offroad ? 3000000U : 15000000U;
  const uint8_t session_frames = offroad ? 30U : 150U;
  const bool session = new_session || ((safety_get_ts_elapsed(now, ambient_session_ts) < session_us) &&
                                       (ambient_session_count < session_frames));
  const bool allowed = fresh && target && red && matches_template && rate && session;
  if (allowed) {
    if (new_session) {
      ambient_session_ts = now;
      ambient_session_count = 0U;
    }
    ambient_session_count++;
    ambient_tx_valid = true;
    ambient_tx_ts = now;
  }
  return allowed;
}

static void ambient_reset(void) {
  ambient_template_valid = false;
  ambient_tx_valid = false;
  ambient_template_ts = 0U;
  ambient_tx_ts = 0U;
  ambient_session_ts = 0U;
  ambient_session_count = 0U;
}

static const safety_plugin ambient_light_plugin = {
  .msg = {0x679, 1, 7, .check_relay = false, .disable_static_blocking = true},
  .active = ambient_active,
  .rx = ambient_rx,
  .tx = ambient_tx,
  .reset = ambient_reset,
};
