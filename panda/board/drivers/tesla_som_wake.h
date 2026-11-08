#pragma once

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#include "opendbc/safety/can.h"

// Cabin entry after the SOM has powered off. This is not ignition.
// ignition_can stays vehiclePowerState DRIVE so openpilot does not go
// onroad in Park. main.c ORs this into bootkick only once the SOM
// heartbeat is gone, which is the same GPIO a timed bootkick pulses.

static bool tesla_som_wake = false;
static uint32_t tesla_som_wake_cnt = 0U;
static uint8_t tesla_di_prev = 0xFFU;
static uint8_t tesla_esp_prev = 0xFFU;
static uint8_t tesla_pwr_prev = 0xFFU;

// cppcheck-suppress unusedFunction ; the host test resets state between cases
static void tesla_som_wake_reset(void) {
  tesla_som_wake = false;
  tesla_som_wake_cnt = 0U;
  tesla_di_prev = 0xFFU;
  tesla_esp_prev = 0xFFU;
  tesla_pwr_prev = 0xFFU;
}

static uint8_t tesla_wake_bits(const CANPacket_t *msg, uint8_t start, uint8_t length) {
  uint8_t byte = start / 8U;
  uint8_t shift = start % 8U;
  uint8_t mask = (uint8_t)((1U << length) - 1U);
  uint16_t raw = msg->data[byte];
  if ((uint8_t)(shift + length) > 8U) {
    raw |= (uint16_t)((uint16_t)msg->data[(uint8_t)(byte + 1U)] << 8);
  }
  return (uint8_t)((raw >> shift) & mask);
}

static bool tesla_counter_ok(uint8_t *prev, uint8_t counter) {
  uint8_t seen = *prev;
  *prev = counter;
  return (seen != 0xFFU) && (counter == (uint8_t)((seen + 1U) & 0x0FU));
}

static bool tesla_wake_bus(const CANPacket_t *msg) {
  return (msg->bus == 0U) || (msg->bus == 2U);
}

static void tesla_som_wake_set(bool wake) {
  if (wake) {
    tesla_som_wake = true;
    tesla_som_wake_cnt = 0U;
  }
}

// DI_systemStatus 0x118, ESP_status 0x145, VCFRONT_LVPowerState 0x221.
// Party bus is CAN0, or CAN2 when the harness is flipped. Power-save keeps
// exactly one of those controllers interrupting.
static void tesla_som_wake_hook(const CANPacket_t *msg) {
  bool wake = false;
  if ((msg != NULL) && tesla_wake_bus(msg) && (GET_LEN(msg) >= 8U)) {
    uint32_t addr = msg->addr;
    if (addr == 0x118U) {
      if (tesla_counter_ok(&tesla_di_prev, tesla_wake_bits(msg, 8U, 4U))) {
        uint8_t gear = tesla_wake_bits(msg, 21U, 3U);
        uint8_t brake = tesla_wake_bits(msg, 19U, 2U);
        // DI_gear R/N/D. Park is 1. 0 and 7 are invalid. DI_brakePedalState ON is 1.
        wake = (brake == 1U) || (gear == 2U) || (gear == 3U) || (gear == 4U);
      }
    } else if (addr == 0x145U) {
      if (tesla_counter_ok(&tesla_esp_prev, tesla_wake_bits(msg, 8U, 4U))) {
        // ESP_driverBrakeApply DRIVER_APPLYING is 2.
        wake = tesla_wake_bits(msg, 29U, 2U) == 2U;
      }
    } else if (addr == 0x221U) {
      if (tesla_counter_ok(&tesla_pwr_prev, tesla_wake_bits(msg, 52U, 4U))) {
        uint8_t power = tesla_wake_bits(msg, 5U, 2U);
        // ACCESSORY=2 is the cabin-on state that comes with the brake.
        // DRIVE=3 is the same edge ignition_can already bootkicks.
        // CONDITIONING=1 is precondition, not the driver getting in.
        wake = (power == 2U) || (power == 3U);
      }
    } else {
      wake = false;
    }
  }
  tesla_som_wake_set(wake);
}

// 1 Hz, same ageing as ignition_can. Two quiet seconds drops the request
// so the next brake press is a new bootkick edge.
static void tesla_som_wake_tick(void) {
  if (tesla_som_wake_cnt > 2U) {
    tesla_som_wake = false;
  }
  if (tesla_som_wake_cnt < 0xFFFFFFFFU) {
    tesla_som_wake_cnt += 1U;
  }
}
