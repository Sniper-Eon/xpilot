#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "opendbc/safety/can.h"
#include "opendbc/safety/helpers.h"

bool ignition_can = false;
uint32_t ignition_can_cnt = 0U;

void ignition_can_hook(const CANPacket_t *msg) {
  // Tesla Model 3/Y exception
  if (msg_matches(msg, 0x221U, 0U, 8U)) {
    int counter = msg->data[6] >> 4;

    static int prev_counter_tesla = -1;
    if ((counter == ((prev_counter_tesla + 1) % 16)) && (prev_counter_tesla != -1)) {
      // VCFRONT_LVPowerState->VCFRONT_vehiclePowerState
      int power_state = (msg->data[0] >> 5U) & 0x3U;
      ignition_can = power_state == 0x3;  // VEHICLE_POWER_STATE_DRIVE=3
      ignition_can_cnt = 0U;
    }
    prev_counter_tesla = counter;
  }
}
