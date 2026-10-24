/* Recursion checks stack frames, live locals and preserved return addresses. */
int triangle(int n) {
  if (n <= 0) {
    return 0;
  }
  return n + triangle(n - 1);
}

int adjust(int value, int bias) {
  return value + bias + triangle(5);
}
