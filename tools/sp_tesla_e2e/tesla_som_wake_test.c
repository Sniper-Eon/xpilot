#include <stdio.h>
#include <string.h>

#include "panda/board/drivers/tesla_som_wake.h"

static int failures = 0;

static void expect(int cond, const char *name) {
  if (!cond) {
    fprintf(stderr, "fail %s wake=%d\n", name, tesla_som_wake ? 1 : 0);
    failures += 1;
  }
}

static void put_bits(uint8_t *data, unsigned start, unsigned length, unsigned value) {
  unsigned i;
  for (i = 0U; i < length; i++) {
    unsigned bit = start + i;
    unsigned byte = bit / 8U;
    unsigned shift = bit % 8U;
    if (((value >> i) & 1U) != 0U) {
      data[byte] = (uint8_t)(data[byte] | (uint8_t)(1U << shift));
    }
  }
}

static CANPacket_t frame(uint32_t addr, uint8_t bus, uint8_t counter, unsigned gear, unsigned brake, unsigned esp_brake, unsigned power) {
  CANPacket_t msg;
  uint8_t data[8] = {0, 0, 0, 0, 0, 0, 0, 0};
  memset(&msg, 0, sizeof(msg));
  if (addr == 0x118U) {
    put_bits(data, 8U, 4U, counter);
    put_bits(data, 21U, 3U, gear);
    put_bits(data, 19U, 2U, brake);
  } else if (addr == 0x145U) {
    put_bits(data, 8U, 4U, counter);
    put_bits(data, 29U, 2U, esp_brake);
  } else {
    put_bits(data, 52U, 4U, counter);
    put_bits(data, 5U, 2U, power);
  }
  msg.addr = addr;
  msg.bus = bus;
  msg.data_len_code = 8U;
  memcpy(msg.data, data, 8U);
  return msg;
}

static void send(uint32_t addr, uint8_t bus, uint8_t counter, unsigned gear, unsigned brake, unsigned esp_brake, unsigned power) {
  CANPacket_t msg = frame(addr, bus, counter, gear, brake, esp_brake, power);
  tesla_som_wake_hook(&msg);
}

int main(void) {
  CANPacket_t msg;

  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 1U, 1U, 0U, 0U);
  expect(!tesla_som_wake, "first DI frame is not a wake");
  send(0x118U, 0U, 1U, 1U, 1U, 0U, 0U);
  expect(tesla_som_wake, "brake in Park wakes");

  tesla_som_wake_reset();
  send(0x118U, 0U, 4U, 1U, 0U, 0U, 0U);
  send(0x118U, 0U, 5U, 1U, 0U, 0U, 0U);
  expect(!tesla_som_wake, "Park without brake does not wake");

  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 4U, 0U, 0U, 0U);
  send(0x118U, 0U, 1U, 4U, 0U, 0U, 0U);
  expect(tesla_som_wake, "gear D wakes");
  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 2U, 0U, 0U, 0U);
  send(0x118U, 0U, 1U, 2U, 0U, 0U, 0U);
  expect(tesla_som_wake, "gear R wakes");
  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 3U, 0U, 0U, 0U);
  send(0x118U, 0U, 1U, 3U, 0U, 0U, 0U);
  expect(tesla_som_wake, "gear N wakes");

  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 0U, 0U, 0U, 0U);
  send(0x118U, 0U, 1U, 0U, 0U, 0U, 0U);
  expect(!tesla_som_wake, "invalid gear does not wake");
  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 7U, 0U, 0U, 0U);
  send(0x118U, 0U, 1U, 7U, 0U, 0U, 0U);
  expect(!tesla_som_wake, "SNA gear does not wake");

  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 4U, 1U, 0U, 0U);
  send(0x118U, 0U, 2U, 4U, 1U, 0U, 0U);
  expect(!tesla_som_wake, "skipped counter does not wake");

  tesla_som_wake_reset();
  send(0x118U, 1U, 0U, 4U, 1U, 0U, 0U);
  send(0x118U, 1U, 1U, 4U, 1U, 0U, 0U);
  expect(!tesla_som_wake, "bus 1 does not wake");

  tesla_som_wake_reset();
  msg = frame(0x118U, 0U, 1U, 4U, 1U, 0U, 0U);
  msg.data_len_code = 1U;
  tesla_som_wake_hook(&msg);
  expect(!tesla_som_wake, "short frame does not wake");

  tesla_som_wake_reset();
  send(0x145U, 2U, 7U, 0U, 0U, 2U, 0U);
  send(0x145U, 2U, 8U, 0U, 0U, 2U, 0U);
  expect(tesla_som_wake, "ESP brake on the flipped bus wakes");
  tesla_som_wake_reset();
  send(0x145U, 0U, 0U, 0U, 0U, 1U, 0U);
  send(0x145U, 0U, 1U, 0U, 0U, 1U, 0U);
  expect(!tesla_som_wake, "ESP brake not applied does not wake");

  tesla_som_wake_reset();
  send(0x221U, 0U, 0U, 0U, 0U, 0U, 2U);
  send(0x221U, 0U, 1U, 0U, 0U, 0U, 2U);
  expect(tesla_som_wake, "accessory power wakes");
  tesla_som_wake_reset();
  send(0x221U, 0U, 0U, 0U, 0U, 0U, 3U);
  send(0x221U, 0U, 1U, 0U, 0U, 0U, 3U);
  expect(tesla_som_wake, "drive power wakes");
  tesla_som_wake_reset();
  send(0x221U, 0U, 0U, 0U, 0U, 0U, 1U);
  send(0x221U, 0U, 1U, 0U, 0U, 0U, 1U);
  expect(!tesla_som_wake, "conditioning does not wake");
  tesla_som_wake_reset();
  send(0x221U, 0U, 15U, 0U, 0U, 0U, 2U);
  send(0x221U, 0U, 0U, 0U, 0U, 0U, 2U);
  expect(tesla_som_wake, "counter wrap wakes");

  tesla_som_wake_reset();
  send(0x118U, 0U, 0U, 1U, 1U, 0U, 0U);
  send(0x118U, 0U, 1U, 1U, 1U, 0U, 0U);
  expect(tesla_som_wake, "wake latched");
  tesla_som_wake_tick();
  tesla_som_wake_tick();
  tesla_som_wake_tick();
  expect(tesla_som_wake, "still latched inside the quiet window");
  tesla_som_wake_tick();
  expect(!tesla_som_wake, "quiet bus drops the wake");

  return failures == 0 ? 0 : 1;
}
