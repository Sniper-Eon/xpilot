#pragma once

// xpilot safety plugin interface (see XPILOT.md at the repo root).
// A plugin owns exactly one extra TX message. It never relaxes the active safety mode: the mode's own
// allowlist and checks are untouched, and the plugin's message is sent only if its own tx() validates it.
typedef struct {
  CanMsg msg;                             // the one message (addr, bus, len) this plugin may send
  bool (*active)(void);                   // mode / param gate, evaluated per message
  void (*rx)(const CANPacket_t *msg);     // called for every valid RX message (templates, state)
  bool (*tx)(const CANPacket_t *msg);     // validate one TX of msg; true = allowed
  void (*reset)(void);                    // called on every safety mode change
} safety_plugin;
