#pragma once

// xpilot plugin "auto_speed": one right scroll-wheel tick on VCLEFT_switchStatus (0x3C2, vehicle bus 1),
// cloned from a fresh idle frame the car sent. Python side: openpilot/tesla/plugins/auto_speed/.
#define XPILOT_PARAM_SP_AUTO_SPEED 0x4000U  // CarParamsSP.safetyParam bit set by the plugin when enabled

static bool auto_speed_template_valid = false;
static uint8_t auto_speed_template[8] = {0U};
static uint32_t auto_speed_template_ts = 0U;
static bool auto_speed_last_tx_valid = false;
static uint32_t auto_speed_last_tx_ts = 0U;

static bool auto_speed_active(void) {
  return (current_safety_mode == SAFETY_TESLA) && tesla_has_vehicle_bus &&
         GET_FLAG(current_safety_param_sp, XPILOT_PARAM_SP_AUTO_SPEED);
}

static void auto_speed_rx(const CANPacket_t *msg) {
  // Keep only fresh idle mux-1 frames: TX may clone them and change the tick bits alone.
  if ((msg->bus == 1U) && (msg->addr == 0x3C2U) && (GET_LEN(msg) == 8U) &&
      ((msg->data[0] & 0x03U) == 1U) && ((msg->data[3] & 0x3FU) == 0U)) {
    for (uint8_t i = 0U; i < 8U; i++) {
      auto_speed_template[i] = msg->data[i];
    }
    auto_speed_template_ts = microsecond_timer_get();
    auto_speed_template_valid = true;
  }
}

static bool auto_speed_tx(const CANPacket_t *msg) {
  const uint8_t ticks = msg->data[3] & 0x3FU;
  const bool tick_allowed = (ticks == 1U) || (ticks == 0x3FU);
  bool template_matches = (msg->data[3] & 0xC0U) == (auto_speed_template[3] & 0xC0U);
  for (uint8_t i = 0U; i < 8U; i++) {
    if (i != 3U) {
      template_matches = template_matches && (msg->data[i] == auto_speed_template[i]);
    }
  }
  const uint32_t now = microsecond_timer_get();
  const bool template_fresh = auto_speed_template_valid && (safety_get_ts_elapsed(now, auto_speed_template_ts) <= 1500000U);
  const bool rate_allowed = !auto_speed_last_tx_valid || (safety_get_ts_elapsed(now, auto_speed_last_tx_ts) >= 250000U);
  const bool allowed = controls_allowed && tick_allowed && template_matches && template_fresh && rate_allowed;
  if (allowed) {
    auto_speed_last_tx_valid = true;
    auto_speed_last_tx_ts = now;
  }
  return allowed;
}

static void auto_speed_reset(void) {
  auto_speed_template_valid = false;
  auto_speed_last_tx_valid = false;
  auto_speed_template_ts = 0U;
  auto_speed_last_tx_ts = 0U;
}

static const safety_plugin auto_speed_plugin = {
  .msg = {0x3C2, 1, 8, .check_relay = false, .disable_static_blocking = true},
  .active = auto_speed_active,
  .rx = auto_speed_rx,
  .tx = auto_speed_tx,
  .reset = auto_speed_reset,
};
