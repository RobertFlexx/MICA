// MICA 2.0 structural decoder. Reserved 2C compact forms require feature bit 8.
// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
namespace mica {
// Feature bitmap is identical to the architectural features CSR.
inline bool legal_encoding(std::uint16_t h, std::uint32_t p, int width,
                           unsigned features = 511) {
  auto reg = [&](unsigned n) { return n < 8 || (features & 1); };
  const unsigned cls = h >> 14, op8 = (h >> 6) & 255;
  if (cls == 0) {
    const unsigned d = (h >> 3) & 7, s = h & 7;
    if (op8 >= 23 && op8 <= 30)
      return (features & 4) && s && s != d &&
             (width == 64 || ((op8 - 23) & 3) != 3);
    if (op8 == 41)
      return (features & 256) && d == 0 && s == 0;
    if (op8 == 31 || op8 == 32)
      return (features & 256) != 0;
    if (op8 >= 33 && op8 <= 40)
      return (features & 256) && d != 0;
    if (op8 > 22)
      return false;
    if (op8 == 0 || op8 >= 18)
      return !d && !s && (op8 != 21 || (features & 64));
    if (op8 >= 13 && op8 <= 16)
      return !s;
    return op8 != 17 || (features & 2);
  }
  if (cls == 1) {
    const unsigned op = (h >> 11) & 7;
    return (op != 3 && op != 4) || (h & 255) < 32;
  }
  if (cls == 2)
    return true;
  const unsigned major = (h >> 10) & 15;
  const unsigned op = p >> 20, d = (p >> 16) & 15, a = (p >> 12) & 15,
                 b = (p >> 8) & 15;
  const unsigned op4 = p >> 22, d4 = (p >> 18) & 15, a4 = (p >> 14) & 15;
  switch (major) {
  case 0:
  case 7:
  case 11:
    if ((p & 255) || !reg(d) || !reg(a) || !reg(b))
      return false;
    if (major == 0)
      return op <= 11 && (op != 11 || (features & 2));
    if (major == 7)
      return width == 64 && op <= 8 && (op != 8 || (features & 2));
    return (features & 32) && op <= 19 && ((op > 3 && op < 17) || !b);
  case 1:
    return op4 <= 6 && reg(d4) && reg(a4) &&
           (op4 < 4 || (p & 16383) < unsigned(width));
  case 2:
    return op <= 3 && (op != 3 || (features & 256)) && reg(d);
  case 3:
    return op4 <= 5 && reg(d4) && reg(a4);
  case 4:
    return (p >> 24) <= 1;
  case 5:
    if (!reg(d) || !reg(a) || !reg(b))
      return false;
    if (op == 0)
      return !a && !b;
    if (op == 1)
      return !d && !b;
    return (features & 8) && op <= 9 && !(p & 255) && (op < 6 || width == 64) &&
           ((op != 2 && op != 6) || !b);
  case 6: {
    if (!(features & 16) || op > 21 || (p & 63))
      return false;
    if (op == 16 || op == 17)
      return !(p & 0x3fff);
    const unsigned mode = (p >> 6) & 7, lane = (p >> 9) & 3;
    return (!(mode & 2) || op <= 2) && (!(mode & 4) || op == 7 || op == 8) &&
           (op != 15 || !lane) && ((op != 13 && op != 14) || !((p >> 11) & 7));
  }
  case 8:
    return width == 64 && op4 <= 5 && reg(d4) && reg(a4);
  case 9:
    return (features & 4) && !(p >> 24) && ((p >> 20) & 15) &&
           reg((p >> 20) & 15);
  case 10:
    return (features & 4) && op4 <= 10 && (op4 < 8 || (features & 256)) &&
           reg(d4) && reg(a4) && a4 && a4 != d4 &&
           (op4 >= 8 || width == 64 || (op4 & 3) != 3);
  default:
    return false;
  }
}
} // namespace mica
