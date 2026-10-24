/* Simulated platform: exact-address volatile MMIO, no host device access. */
void platform_init(void) {
  *(volatile unsigned int *)0xffff0064u = 0;
  *(volatile unsigned int *)0xffff0068u = 250000;
  *(volatile unsigned int *)0xffff0060u = 1;
}
void platform_put_byte(unsigned int value) {
  *(volatile unsigned int *)0xffff0000u = value;
}
void platform_kick(void) {
  *(volatile unsigned int *)0xffff006cu = 1;
}
unsigned int platform_faults(void) {
  return *(volatile unsigned int *)0xffff0070u;
}
