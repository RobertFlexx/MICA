/* Finite sensor-node simulation: four timer wakes, CRC-8 packets and supervision. */
void platform_init(void);
void platform_wait_tick(void);
void platform_put_byte(unsigned int value);
void platform_kick(void);
unsigned int platform_faults(void);

unsigned char sensor_samples[4] = {100, 101, 102, 103};
volatile unsigned int measurement_count = 0;

unsigned int crc8_byte(unsigned int crc, unsigned int value) {
  crc ^= value;
  for (unsigned int bit = 0; bit < 8; ++bit) {
    if (crc & 128u) {
      crc = (crc << 1) ^ 7u;
    } else {
      crc <<= 1;
    }
    crc &= 255u;
  }
  return crc;
}

int main(void) {
  platform_init();
  for (unsigned int sequence = 0; sequence < 4; ++sequence) {
    platform_wait_tick();
    unsigned int sample = sensor_samples[sequence];
    unsigned int crc = crc8_byte(crc8_byte(0, sequence), sample);
    platform_put_byte(165);
    platform_put_byte(sequence);
    platform_put_byte(sample);
    platform_put_byte(crc);
    platform_kick();
    measurement_count += 1;
  }
  if (platform_faults() != 0) {
    return -1;
  }
  return 42;
}
