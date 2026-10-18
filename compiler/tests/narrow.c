/* Narrow signedness, pointer arithmetic, four arguments and aligned globals. */
unsigned char bytes[4] __attribute__((aligned(32))) = {0, 127, 128, 255};
int mix(short a, unsigned char b, int c, unsigned int d) {
  int result = a + b;
  if (a < 0) {
    result += c;
  }
  if (d >= 0x80000000u) {
    result ^= 123;
  }
  return result;
}
int main(void) {
  short signed_value = -32768;
  unsigned char *p = bytes + 3;
  int result = mix(signed_value, *p, 9, 0x80000001u);
  p -= 2;
  return result + *p + (int)(((unsigned int)result) >> 17);
}
