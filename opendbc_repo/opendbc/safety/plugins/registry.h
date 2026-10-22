#pragma once

// xpilot safety plugin registry. Add a plugin: write plugins/<name>.h (see plugin.h) and list it here.
#include "opendbc/safety/plugins/plugin.h"
#include "opendbc/safety/plugins/auto_speed.h"
#include "opendbc/safety/plugins/ambient_light.h"

static const safety_plugin *const safety_plugins[] = {
  &auto_speed_plugin,
  &ambient_light_plugin,
};
#define SAFETY_PLUGINS_LEN (sizeof(safety_plugins) / sizeof(safety_plugins[0]))

static void safety_plugins_rx(const CANPacket_t *msg) {
  for (uint32_t i = 0U; i < SAFETY_PLUGINS_LEN; i++) {
    if (safety_plugins[i]->active()) {
      safety_plugins[i]->rx(msg);
    }
  }
}

// The active plugin that owns this TX message, or NULL.
static const safety_plugin *safety_plugin_for(const CANPacket_t *msg) {
  const safety_plugin *owner = NULL;
  for (uint32_t i = 0U; i < SAFETY_PLUGINS_LEN; i++) {
    const CanMsg *m = &safety_plugins[i]->msg;
    if ((owner == NULL) && msg_matches(msg, m->addr, m->bus, m->len) && safety_plugins[i]->active()) {
      owner = safety_plugins[i];
    }
  }
  return owner;
}

static void safety_plugins_reset(void) {
  for (uint32_t i = 0U; i < SAFETY_PLUGINS_LEN; i++) {
    safety_plugins[i]->reset();
  }
}
