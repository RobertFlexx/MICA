/* Integer control flow, global arrays, struct layout and cross-object calls. */
struct sample {
  int value;
  short bias;
};

unsigned int samples[4] = {7, 11, 19, 23};
int adjust(int value, int bias);

int main(void) {
  struct sample state;
  state.value = 0;
  state.bias = -9;
  for (int i = 0; i < 4; ++i) {
    state.value += (int)samples[i];
  }
  if (state.value > 32) {
    state.value = adjust(state.value, state.bias);
  } else {
    state.value = -1;
  }
  return state.value;
}
