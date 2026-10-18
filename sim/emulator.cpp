// MICA-32/64 v1.0 functional ISA emulator, deliberately not cycle accurate.
// SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
#include <sstream>
#include <set>
#include "../isa/generated/profiles.hpp"
#include "../isa/encoding.hpp"
#include "../toolchain/common/elf.hpp"
using U = std::uint64_t;
using S = std::int64_t;
__extension__ typedef __int128 I128;
__extension__ typedef unsigned __int128 U128;
using V = std::array<std::uint8_t, 16>;
struct Fault : std::runtime_error {
  U cause, value;
  explicit Fault(const std::string &message, U reason = 2, U address = 0)
      : std::runtime_error(message), cause(reason), value(address) {}
};
static U mask(int width) {
  return width == 64 ? ~U(0) : ((U(1) << width) - 1);
}
static S sx(U v, int width) {
  if (width == 64)
    return std::bit_cast<S>(v);
  U sign = U(1) << (width - 1);
  return std::bit_cast<S>((v ^ sign) - sign);
}
static U ash(U n, int shift, int width) {
  return U(sx(n, width) >> shift) & mask(width);
}
class CPU {
  std::vector<std::uint8_t> ram;
  std::array<U, 16> x{};
  std::array<V, 8> v{};
  std::array<U, 256> csr{};
  U pc = 0, cycles = 0, retired = 0, reservation = 0;
  U timer = 0, timer_cmp = ~U(0), irq_at = ~U(0), event_order = 0;
  std::ofstream retirement;
  bool recording = false, debug_memory = false;
  struct MemoryEvent {
    U addr, data;
    int bytes;
    bool write;
  };
  std::vector<MemoryEvent> memory_events;
  unsigned features() const {
    return unsigned(xreg) | unsigned(multiply) << 1 | unsigned(flow) << 2 |
           unsigned(atomic) << 3 | unsigned(simd) << 4 | unsigned(bitops) << 5 |
           unsigned(traps) << 6 | 128u | unsigned(mica2) << 8;
  }
  void ram_range(U addr, int n, bool store) {
    if (addr > ram.size() || U(n) > ram.size() - addr)
      throw Fault(store ? "memory write out of bounds"
                        : "memory read out of bounds",
                  store ? 7 : 5, addr);
  }
  int reservation_bytes = 0;
  bool have_reservation = false;
  U led_register = 0;
  std::vector<std::uint8_t> uart_input;
  size_t uart_head = 0;
  bool uart_irq_enable = false;
  std::uint32_t crc_state = 0xffffffffu, crc_count = 0;
  bool halted = false, trace = false, xreg = false, simd = false,
       atomic = false, multiply = false, flow = false, bitops = false,
       traps = false, mica2 = false, sleeping = false;
  int xlen = 32;
  U xmax() {
    return mask(xlen);
  }
  void checkreg(int n) {
    if (n < 0 || n >= 16 || (n >= 8 && !xreg))
      throw Fault("X register disabled");
  }
  U xr(int n) {
    checkreg(n);
    return n ? x[size_t(n)] : 0;
  }
  void wr(int n, U value) {
    checkreg(n);
    if (n)
      x[size_t(n)] = value & xmax();
  }
  U read(U addr, int n) {
    if (n < 1 || n > 8 || (addr % U(n)))
      throw Fault("unaligned memory read", 4, addr);
    U r = 0;
    if (addr == 0xffff0008ULL && n <= 4)
      r = cycles & mask(n * 8);
    else if (addr == 0xffff000cULL && n <= 4)
      r = 0;
    else if (addr == 0xffff0010ULL && n <= 4)
      r = led_register;
    else if (addr == 0xffff0014ULL && n <= 4)
      r = uart_head < uart_input.size() ? uart_input[uart_head++] : 0;
    else if (addr == 0xffff0018ULL && n <= 4)
      r = 8 | (uart_head < uart_input.size() ? 1 : 0) |
          U(uart_input.size() - uart_head) << 8;
    else if (addr == 0xffff001cULL && n <= 4)
      r = uart_irq_enable;
    else if (addr == 0xffff0020ULL && n <= 4)
      r = 3; // Platform devices, separate from ISA extension discovery.
    else if (addr == 0xffff0040ULL && n <= 4)
      r = 0; // Functional device model completes each byte immediately.
    else if (addr == 0xffff0048ULL && n <= 4)
      r = crc_state ^ 0xffffffffu;
    else if (addr == 0xffff004cULL && n <= 4)
      r = crc_count;
    else {
      ram_range(addr, n, false);
      for (int i = 0; i < n; i++)
        r |= U(ram[size_t(addr) + size_t(i)]) << (8 * i);
    }
    r &= mask(n * 8);
    if (recording)
      memory_events.push_back({addr, r, n, false});
    return r;
  }
  void write(U addr, U value, int n) {
    if (n < 1 || n > 8 || (addr % U(n)))
      throw Fault("unaligned memory write", 6, addr);
    value &= mask(n * 8);
    if (addr == 0xffff0000ULL && n <= 4) {
      std::cout.put(char(value & 255));
    } else if (addr == 0xffff0004ULL && n <= 4) {
      exit_value = value & 0xffffffffULL;
      halted = true;
    } else if (addr == 0xffff0010ULL && n <= 4) {
      led_register = value & 255;
    } else if (addr == 0xffff001cULL && n <= 4) {
      uart_irq_enable = value & 1;
    } else if (addr == 0xffff0040ULL && n <= 4) {
      if (value & 1) {
        crc_state = 0xffffffffu;
        crc_count = 0;
      }
    } else if (addr == 0xffff0044ULL && n <= 4) {
      crc_state ^= std::uint32_t(value & 255);
      for (int i = 0; i < 8; ++i)
        crc_state = (crc_state >> 1) ^ ((crc_state & 1) ? 0xedb88320u : 0u);
      ++crc_count;
    } else {
      ram_range(addr, n, true);
      for (int i = 0; i < n; i++)
        ram[size_t(addr) + size_t(i)] = std::uint8_t(value >> (8 * i));
    }
    if (recording)
      memory_events.push_back({addr, value, n, true});
    if (have_reservation && addr <= reservation + U(reservation_bytes - 1) &&
        reservation <= addr + U(n - 1))
      have_reservation = false;
  }
  U csr_read(unsigned id) {
    if (id == 0)
      return 0;
    if (id == 7)
      return cycles & 0xffffffffULL;
    if (id == 8)
      return cycles >> 32;
    if (id == 15)
      return features();
    if (id == 16)
      return U(xlen);
    if (id == 17)
      return retired & 0xffffffffULL;
    if (id == 18)
      return retired >> 32;
    if (id == 13 || id == 14) {
      if (!simd)
        throw Fault("vector CSR unavailable");
      return csr[id];
    }
    if (!traps || id > 19)
      throw Fault("unimplemented CSR");
    if (id == 6)
      return ((csr[6] | U(uart_irq_enable && uart_head < uart_input.size())) &
              1) |
             (timer >= timer_cmp ? 2 : 0);
    if (id == 9)
      return timer & 0xffffffffULL;
    if (id == 10)
      return timer >> 32;
    if (id == 11)
      return timer_cmp & 0xffffffffULL;
    if (id == 12)
      return timer_cmp >> 32;
    return csr[id];
  }
  void csr_write(unsigned id, U value) {
    if (id == 0 || id == 7 || id == 8 || (id >= 15 && id <= 18) || id == 13)
      throw Fault("CSR is read-only");
    if (id == 14) {
      if (!simd)
        throw Fault("vector CSR unavailable");
      csr[id] = value & 1;
      return;
    }
    if (!traps || id > 19)
      throw Fault("unimplemented CSR");
    if ((id == 2 || id == 4) && (value & 1))
      throw Fault("unaligned CSR program address");
    switch (id) {
    case 1:
      csr[1] = (csr[1] & ~U(1)) | (value & 1);
      break;
    case 5:
      csr[5] = value & 3;
      break;
    case 6:
      csr[6] = value & 1;
      break;
    case 9:
      timer = (timer & 0xffffffff00000000ULL) | (value & 0xffffffffULL);
      break;
    case 10:
      timer = (timer & 0xffffffffULL) | ((value & 0xffffffffULL) << 32);
      break;
    case 11:
      timer_cmp = (timer_cmp & 0xffffffff00000000ULL) | (value & 0xffffffffULL);
      break;
    case 12:
      timer_cmp = (timer_cmp & 0xffffffffULL) | ((value & 0xffffffffULL) << 32);
      break;
    default:
      csr[id] = value & xmax();
      break;
    }
  }
  U alu(int op, U a, U b, int width) {
    U z = 0;
    int count = int(b & U(width - 1));
    switch (op) {
    case 0:
      z = a + b;
      break;
    case 1:
      z = a - b;
      break;
    case 2:
      z = a & b;
      break;
    case 3:
      z = a | b;
      break;
    case 4:
      z = a ^ b;
      break;
    case 5:
      z = a << count;
      break;
    case 6:
      z = a >> count;
      break;
    case 7:
      z = ash(a, count, width);
      break;
    case 8:
      z = sx(a, width) < sx(b, width);
      break;
    case 9:
      z = (a & mask(width)) < (b & mask(width));
      break;
    case 10:
      z = a == b;
      break;
    case 11:
      if (!multiply)
        throw Fault("M multiply disabled");
      z = a * b;
      break;
    default:
      throw Fault("illegal ALU operation");
    }
    return z & mask(width);
  }
  static U laneslot(const V &v, int index, int bytes) {
    U r = 0;
    for (int j = 0; j < bytes; j++)
      r |= U(v[size_t(index * bytes + j)]) << (8 * j);
    return r;
  }
  static void setlane(V &v, int index, int bytes, U n) {
    for (int j = 0; j < bytes; j++)
      v[size_t(index * bytes + j)] = std::uint8_t(n >> (8 * j));
  }
  static U sat(I128 n, int bits, bool sign) {
    I128 lo = sign ? -((I128)1 << (bits - 1)) : 0;
    I128 hi = sign         ? (((I128)1 << (bits - 1)) - 1)
              : bits == 64 ? (I128)std::numeric_limits<U>::max()
                           : (((I128)1 << bits) - 1);
    if (n < lo)
      n = lo;
    if (n > hi)
      n = hi;
    return U(n) & mask(bits);
  }
  static U satu(U128 n, int bits) {
    U128 limit = bits == 64 ? (U128)std::numeric_limits<U>::max()
                            : (((U128)1 << bits) - 1);
    return U(n > limit ? limit : n);
  }
  static U shift_round(U a, int shift, int bits, bool sign) {
    if (!shift)
      return a;
    // Quotient toward negative infinity, then nearest-even rounding.
    I128 n = sign ? (I128)sx(a, bits) : (I128)(a & mask(bits));
    I128 q = n >> shift;
    I128 rem = n - q * ((I128)1 << shift);
    I128 half = (I128)1 << (shift - 1);
    if (rem > half || (rem == half && (q & 1)))
      q++;
    return U(q) & mask(bits);
  }
  U bits_alu(int op, U aa, U bb) {
    const U a = aa & xmax(), b = bb & xmax();
    const unsigned shift = unsigned(b & U(xlen - 1));
    switch (op) {
    case 0:
      return a ? U(std::countl_zero(a) - (xlen == 32 ? 32 : 0)) : U(xlen);
    case 1:
      return a ? U(std::countr_zero(a)) : U(xlen);
    case 2:
      return U(std::popcount(a));
    case 3: {
      U z = 0;
      for (int i = 0; i < xlen / 8; i++)
        z = (z << 8) | ((a >> (8 * i)) & 255);
      return z;
    }
    case 4:
      return ((a >> shift) | (a << ((U(xlen) - shift) & U(xlen - 1)))) & xmax();
    case 5:
      return ((a << shift) | (a >> ((U(xlen) - shift) & U(xlen - 1)))) & xmax();
    case 6:
      return sx(a, xlen) < sx(b, xlen) ? a : b;
    case 7:
      return sx(a, xlen) > sx(b, xlen) ? a : b;
    case 8:
      return std::min(a, b);
    case 9:
      return std::max(a, b);
    case 10:
      return a | (U(1) << shift);
    case 11:
      return a & ~(U(1) << shift);
    case 12:
      return a ^ (U(1) << shift);
    case 13:
      return (a >> shift) & 1;
    case 14:
      return a & ~b;
    case 15:
      return a | ~b;
    case 16:
      return ~(a ^ b);
    case 17:
      return U(sx(a & 255, 8));
    case 18:
      return U(sx(a & 65535, 16));
    case 19:
      return a & 65535;
    default:
      throw Fault("illegal bit operation");
    }
  }
  void vecop(U p) {
    if (!csr[14])
      throw Fault("vector state disabled");
    int op = int((p >> 20) & 63), d = int((p >> 17) & 7),
        a = int((p >> 14) & 7), b = int((p >> 11) & 7);
    int bits = 8 << ((p >> 9) & 3), bytes = bits / 8, n = 16 / bytes;
    bool sign = ((p >> 6) & 1) != 0;
    bool saturate = ((p >> 7) & 1) != 0, round = ((p >> 8) & 1) != 0;
    if ((p & 63) || op > 21)
      throw Fault("illegal vector encoding");
    if (op == 16 || op == 17) {
      if ((p & 0x3fff) != 0)
        throw Fault("illegal vld/vst encoding");
      U addr = xr(a);
      if (addr % 16)
        throw Fault("misaligned vector address", op == 17 ? 6 : 4, addr);
      ram_range(addr, 16, op == 17);
      if (op == 16) {
        for (int k = 0; k < 16; k++)
          v[size_t(d)][size_t(k)] = std::uint8_t(read(addr + U(k), 1));
      } else
        for (int k = 0; k < 16; k++)
          write(addr + U(k), v[size_t(d)][size_t(k)], 1);
      csr[13] = 1;
      return;
    }
    if ((saturate && op > 2) || (round && op != 7 && op != 8) ||
        (op == 15 && bits != 8))
      throw Fault("illegal vector modifier");
    V dst{};
    for (int i = 0; i < n; i++) {
      U va = laneslot(v[size_t(a)], i, bytes),
        vb = laneslot(v[size_t(b)], i, bytes), r = 0;
      I128 aa = sign ? (I128)sx(va, bits) : (I128)va;
      I128 bb = sign ? (I128)sx(vb, bits) : (I128)vb;
      int sh = int(vb & U(bits - 1));
      switch (op) {
      case 0:
        r = saturate ? sat(aa + bb, bits, sign) : U(va + vb);
        break;
      case 1:
        r = saturate ? sat(aa - bb, bits, sign) : U(va - vb);
        break;
      case 2:
        r = saturate ? (sign ? sat(aa * bb, bits, true)
                             : satu((U128)va * (U128)vb, bits))
                     : U(va * vb);
        break;
      case 3:
        r = va & vb;
        break;
      case 4:
        r = va | vb;
        break;
      case 5:
        r = va ^ vb;
        break;
      case 6:
        r = va << sh;
        break;
      case 7:
        r = round ? shift_round(va, sh, bits, false) : va >> sh;
        break;
      case 8:
        r = round ? shift_round(va, sh, bits, true) : U(sx(va, bits) >> sh);
        break;
      case 9:
        r = sign ? U(aa <= bb ? va : vb) : std::min(va, vb);
        break;
      case 10:
        r = sign ? U(aa >= bb ? va : vb) : std::max(va, vb);
        break;
      case 11:
        r = va == vb ? mask(bits) : 0;
        break;
      case 12:
        r = aa < bb ? mask(bits) : 0;
        break;
      case 13:
        r = U(aa < 0 ? -aa : aa);
        break;
      case 14:
        r = U(-aa);
        break;
      case 15: {
        I128 dot = 0;
        for (int j = 0; j < 4; j++) {
          U lv = laneslot(v[size_t(a)], i * 4 + j, 1),
            rv = laneslot(v[size_t(b)], i * 4 + j, 1);
          dot += (sign ? (I128)sx(lv, 8) : (I128)lv) *
                 (sign ? (I128)sx(rv, 8) : (I128)rv);
        }
        r = U(dot);
        break;
      }
      case 18:
      case 19: {
        int src = i / 2 + (op == 19 ? n / 2 : 0);
        r = laneslot((i & 1) ? v[size_t(b)] : v[size_t(a)], src, bytes);
        break;
      }
      case 20:
      case 21: {
        int src = (i % (n / 2)) * 2 + (op == 21 ? 1 : 0);
        r = laneslot(i < n / 2 ? v[size_t(a)] : v[size_t(b)], src, bytes);
        break;
      }
      default:
        throw Fault("illegal vector opcode");
      }
      if (op == 15) {
        setlane(dst, i, 4, r);
        if (i == 3)
          break;
      } else
        setlane(dst, i, bytes, r);
    }
    v[size_t(d)] = dst;
    csr[13] = 1;
  }
  // Translate one very common two-instruction counted loop to a native loop.
  // This is NOT a whole-program JIT. Memory, traps, tracing and exotic loops
  // still use the reference engine. Volatile state forces actual iteration,
  // instead of replacing a benchmark with a multiplication and calling it fast.
  U native_counted_loop(U step_budget) {
    if (traps || trace || retirement.is_open() || !flow || pc > ram.size() ||
        ram.size() - size_t(pc) < 6 || (pc & 1))
      return 0;
    const size_t ip = size_t(pc);
    const unsigned hw = unsigned(ram[ip]) | (unsigned(ram[ip + 1]) << 8);
    if ((hw >> 14) != 1 || ((hw >> 11) & 7) != 1)
      return 0; // addi
    const unsigned d = (hw >> 8) & 7;
    if (d == 0)
      return 0;
    const unsigned bh = unsigned(ram[ip + 2]) | (unsigned(ram[ip + 3]) << 8);
    if ((bh >> 14) != 3 || ((bh >> 10) & 15) != 9)
      return 0;
    const U payload =
        (U(bh & 1023) << 16) | U(ram[ip + 4]) | (U(ram[ip + 5]) << 8);
    const unsigned c = unsigned((payload >> 20) & 15);
    if (c == 0 || c == d || (c >= 8 && !xreg) || (payload >> 24) ||
        sx(payload & 0xfffff, 20) != -3)
      return 0;
    const U count = x[c] & xmax();
    if (count == 0 || count > step_budget / 2)
      return 0;
    const U delta = U(sx(hw & 255, 8));
    volatile U result = x[d];
    volatile U left = count;
    while (left != 0) {
      result = result + delta;
      left = left - 1;
    }
    x[d] = result & xmax();
    x[c] = 0;
    pc = (pc + 6) & xmax();
    const U consumed = count * 2;
    retired += consumed;
    cycles += consumed;
    return consumed;
  }
  // Tight path for the common short scalar instructions. Anything involving
  // traps, memory, vectors, atomics or unfamiliar encodings goes through step().
  // Keeping the reference interpreter in the same executable is intentional.
  bool fast_step() {
    if (traps || trace || retirement.is_open() || pc > ram.size() ||
        ram.size() - size_t(pc) < 2 || (pc & 1))
      return false;
    const size_t ip = size_t(pc);
    const unsigned hw = unsigned(ram[ip]) | (unsigned(ram[ip + 1]) << 8);
    const unsigned klass = hw >> 14;
    U next = (pc + 2) & xmax();
    if (klass == 1) {
      const unsigned op = (hw >> 11) & 7, d = (hw >> 8) & 7;
      const U imm = hw & 255u;
      switch (op) {
      case 0:
        x[d] = U(sx(imm, 8)) & xmax();
        break;
      case 1:
        x[d] = (x[d] + U(sx(imm, 8))) & xmax();
        break;
      case 2:
        x[d] &= imm;
        break;
      case 3:
        if (imm > 31)
          return false;
        x[d] = (x[d] << imm) & xmax();
        break;
      case 4:
        if (imm > 31)
          return false;
        x[d] >>= imm;
        break;
      case 5:
        if (!x[d])
          next = (next + U(sx(imm, 8) * 2)) & xmax();
        break;
      case 6:
        if (x[d])
          next = (next + U(sx(imm, 8) * 2)) & xmax();
        break;
      case 7:
        next = (next + U(sx(hw & 2047u, 11) * 2)) & xmax();
        break;
      }
      // x0 is architecturally zero, even for short immediate instructions.
      x[0] = 0;
    } else if (klass == 0) {
      const unsigned op = (hw >> 6) & 255u, d = (hw >> 3) & 7, a = hw & 7;
      switch (op) {
      case 0:
        if (d || a)
          return false;
        break;
      case 1:
        x[d] = x[a];
        break;
      case 2:
        x[d] = (x[d] + x[a]) & xmax();
        break;
      case 3:
        x[d] = (x[d] - x[a]) & xmax();
        break;
      case 4:
        x[d] &= x[a];
        break;
      case 5:
        x[d] |= x[a];
        break;
      case 6:
        x[d] ^= x[a];
        break;
      case 7:
        x[d] = (x[d] << (x[a] & U(xlen - 1))) & xmax();
        break;
      case 8:
        x[d] >>= (x[a] & U(xlen - 1));
        break;
      case 9:
        x[d] = ash(x[d], int(x[a] & U(xlen - 1)), xlen);
        break;
      case 10:
        x[d] = sx(x[d], xlen) < sx(x[a], xlen);
        break;
      case 11:
        x[d] = x[d] < x[a];
        break;
      case 12:
        x[d] = x[d] == x[a];
        break;
      case 13:
        if (a || (x[d] & 1))
          return false;
        next = x[d] & xmax();
        break;
      case 14:
        if (a || (x[d] & 1))
          return false;
        next = x[d] & xmax();
        x[6] = (pc + 2) & xmax();
        break;
      case 15:
        if (a)
          return false;
        x[d] = ~x[d] & xmax();
        break;
      case 16:
        if (a)
          return false;
        x[d] = -x[d] & xmax();
        break;
      case 17:
        if (!multiply)
          return false;
        x[d] = x[d] * x[a] & xmax();
        break;
      case 18:
        if (d || a || mica2)
          return false;
        halted = true;
        break;
      case 19:
      case 22:
        if (d || a)
          return false;
        break;
      case 20:
        if (d || a)
          return false;
        halted = true;
        break;
      default:
        return false;
      }
      x[0] = 0;
    } else if (klass == 3 && flow && ip + 4 <= ram.size()) {
      const unsigned major = (hw >> 10) & 15;
      if (major != 9)
        return false;
      const U payload =
          U(hw & 1023u) << 16 | U(ram[ip + 2]) | (U(ram[ip + 3]) << 8);
      if ((payload >> 24) || ((payload >> 20) & 15u) == 0)
        return false;
      const unsigned d = unsigned(payload >> 20) & 15u;
      if (d >= 8 && !xreg)
        return false;
      x[d] = (x[d] - 1) & xmax();
      next = (pc + 4) & xmax();
      if (x[d])
        next = (next + U(sx(payload & 0xfffffu, 20) * 2)) & xmax();
    } else
      return false;
    pc = next;
    ++cycles;
    ++retired;
    return true;
  }
  void enter_trap(U cause, U saved_pc, U value = 0) {
    if ((csr[4] & 1) || csr[4] == 0 || csr[4] >= ram.size())
      throw Fault("invalid trap vector");
    if (csr[1] & 4)
      throw Fault("double trap without handler stack");
    csr[2] = saved_pc & xmax();
    csr[3] = cause & xmax();
    csr[19] = value & xmax();
    csr[1] = (csr[1] & ~U(7)) | ((csr[1] & 1) ? U(2) : U(0)) | 4;
    pc = csr[4];
    have_reservation = false;
  }
  void step() {
    if (pc % 2)
      throw Fault("invalid fetch alignment", 0, pc);
    if (pc > ram.size() || ram.size() - size_t(pc) < 2)
      throw Fault("instruction access fault", 1, pc);
    U here = pc;
    U hw = read(pc, 2), klass = hw >> 14;
    int size = klass == 3 ? 4 : 2;
    if (ram.size() - size_t(pc) < U(size))
      throw Fault("truncated 32-bit instruction", 1, pc + 2);
    U p = klass == 3 ? (((hw & 1023) << 16) | read(pc + 2, 2)) : 0;
    if (!mica::legal_encoding(std::uint16_t(hw), std::uint32_t(p), xlen,
                              features()))
      throw Fault("illegal instruction encoding", 2, hw | ((p & 65535) << 16));
    pc = (pc + U(size)) & xmax();
    recording = retirement.is_open() || debug_memory;
    if (trace)
      std::cerr << "pc=" << std::hex << here << " ins=" << hw
                << (size == 4 ? " ext" : "") << std::dec << "\n";
    if (klass == 0) {
      int op = int((hw >> 6) & 255), d = int((hw >> 3) & 7), s = int(hw & 7);
      if (op >= 23 && op <= 30) {
        if (!flow || s == 0 || s == d)
          throw Fault("illegal compact flow instruction");
        int code = op - 23, bytes = 1 << (code & 3);
        if (bytes == 8 && xlen != 64)
          throw Fault("flow q operation requires XLEN64");
        U addr = xr(s);
        if (code < 4)
          wr(d, read(addr, bytes));
        else
          write(addr, xr(d), bytes);
        wr(s, addr + U(bytes));
      } else if (op == 41) {
        if (!mica2 || d != 0 || s != 0)
          throw Fault("illegal stop encoding");
        halted = true;
      } else if (op == 31 || op == 32) {
        if (!mica2)
          throw Fault("MICA2 stack encoding disabled");
        const U addr = (xr(7) + U(s * (xlen / 8))) & xmax();
        if (op == 31)
          wr(d, read(addr, xlen / 8));
        else
          write(addr, xr(d), xlen / 8);
      } else if (op >= 33 && op <= 40) {
        if (!mica2 || d == 0)
          throw Fault("illegal compact counter branch");
        const U result = (xr(d) - 1) & xmax();
        wr(d, result);
        if (result)
          pc = (pc + U(sx(U(((op - 33) << 3) | s), 6) * 2)) & xmax();
      } else if (op == 1)
        wr(d, xr(s));
      else if ((op >= 2 && op <= 12) || op == 17) {
        if (op == 17 && !multiply)
          throw Fault("M disabled");
        wr(d, alu(op == 17 ? 11 : op - 2, xr(d), xr(s), xlen));
      } else if (op == 0) {
        if (d || s)
          throw Fault("bad nop reserved bits");
      } else if (op == 13 || op == 14) {
        if (s)
          throw Fault("bad jump reserved bits");
        U target = xr(d);
        if (target & 1)
          throw Fault("unaligned jump target", 0, target);
        if (op == 14)
          wr(6, pc);
        pc = target;
      } else if (op == 15 || op == 16) {
        if (s)
          throw Fault("bad unary reserved bits");
        wr(d, op == 15 ? ~xr(d) : U(0) - xr(d));
      } else if (op == 18 || op == 20) {
        if (d || s)
          throw Fault("bad system reserved bits");
        if (op == 20 && traps)
          enter_trap(11, mica2 ? here : pc);
        else if (op == 18 && mica2)
          sleeping = true;
        else
          halted = true;
      } else if (op == 19 || op == 22) {
        if (d || s)
          throw Fault("bad fence reserved bits");
      } else if (op == 21) {
        if (d || s)
          throw Fault("bad eret reserved bits");
        if (traps) {
          if (!(csr[1] & 4))
            throw Fault("eret outside trap");
          if (csr[2] & 1)
            throw Fault("unaligned return target", 0, csr[2]);
          pc = csr[2] & xmax();
          csr[1] = (csr[1] & ~U(7)) | ((csr[1] & 2) ? U(1) : U(0));
        } else
          pc = csr[2];
      } else
        throw Fault("illegal short R opcode");
    } else if (klass == 1) {
      int op = int((hw >> 11) & 7), d = int((hw >> 8) & 7);
      U imm = hw & 255;
      if (op == 7) {
        U off = hw & 2047;
        pc = pc + U(sx(off, 11) * 2);
      } else if (op == 5 || op == 6) {
        if ((xr(d) == 0) == (op == 5))
          pc = pc + U(sx(imm, 8) * 2);
      } else if (op == 0)
        wr(d, U(sx(imm, 8)));
      else if (op == 1)
        wr(d, xr(d) + U(sx(imm, 8)));
      else if (op == 2)
        wr(d, xr(d) & imm);
      else if (op == 3 || op == 4) {
        if (imm > 31)
          throw Fault("reserved short shift bits");
        wr(d, op == 3 ? (xr(d) << imm) : (xr(d) >> imm));
      } else
        throw Fault("illegal short immediate");
    } else if (klass == 2) {
      int op = int((hw >> 11) & 7), d = int((hw >> 8) & 7),
          b = int((hw >> 5) & 7);
      S off = sx(hw & 31, 5) * S(op == 0 || op == 1              ? 4
                                 : op == 2 || op == 3 || op == 6 ? 2
                                                                 : 1);
      U addr = (xr(b) + U(off)) & xmax();
      int n = op == 0 || op == 1 ? 4 : op == 2 || op == 3 || op == 6 ? 2 : 1;
      if (op == 1 || op == 3 || op == 5)
        write(addr, xr(d), n);
      else {
        U z = read(addr, n);
        if (op == 2 || op == 4 || (op == 0 && mica2 && xlen == 64))
          z = U(sx(z, n * 8));
        wr(d, z);
      }
    } else {
      int maj = int((hw >> 10) & 15);
      if (maj == 0 || maj == 7) {
        int op = int((p >> 20) & 63), d = int((p >> 16) & 15),
            a = int((p >> 12) & 15), b = int((p >> 8) & 15);
        if ((p & 255) || op > (maj == 7 ? 8 : 11))
          throw Fault("bad extended ALU encoding");
        if (maj == 7) {
          if (xlen != 64)
            throw Fault("W32 only XLEN64");
          if (op == 8 && !multiply)
            throw Fault("M disabled");
          U aa = xr(a) & 0xffffffffULL, bb = xr(b) & 0xffffffffULL, zz = 0;
          if (op == 0)
            zz = aa + bb;
          else if (op == 1)
            zz = aa - bb;
          else if (op == 2)
            zz = aa << (bb & 31);
          else if (op == 3)
            zz = aa >> (bb & 31);
          else if (op == 4)
            zz = ash(aa, int(bb & 31), 32);
          else if (op == 5)
            zz = aa & bb;
          else if (op == 6)
            zz = aa | bb;
          else if (op == 7)
            zz = aa ^ bb;
          else
            zz = aa * bb;
          wr(d, U(sx(zz & 0xffffffffULL, 32)));
        } else
          wr(d, alu(op, xr(a), xr(b), xlen));
      } else if (maj == 1) {
        int op = int((p >> 22) & 15), d = int((p >> 18) & 15),
            a = int((p >> 14) & 15);
        U imm = p & 16383;
        if (op > 6)
          throw Fault("illegal immediate opcode");
        U z = 0, aa = xr(a);
        if (op == 0)
          z = aa + U(sx(imm, 14));
        else if (op == 1)
          z = aa & imm;
        else if (op == 2)
          z = aa | imm;
        else if (op == 3)
          z = aa ^ imm;
        else if (op == 4) {
          if (imm >= U(xlen))
            throw Fault("shift too large");
          z = aa << imm;
        } else if (op == 5) {
          if (imm >= U(xlen))
            throw Fault("shift too large");
          z = aa >> imm;
        } else {
          if (imm >= U(xlen))
            throw Fault("shift too large");
          z = ash(aa, int(imm), xlen);
        }
        wr(d, z);
      } else if (maj == 2) {
        int op = int((p >> 20) & 63), d = int((p >> 16) & 15);
        U imm = p & 65535;
        if (op > 3 || (op == 3 && !mica2))
          throw Fault("illegal wide opcode");
        if (op == 0)
          wr(d, imm << 16);
        else if (op == 1)
          wr(d, (xr(d) & ~U(65535)) | imm);
        else if (op == 3)
          wr(d, (here + U(sx(imm, 16) * 2)) & xmax());
        else
          wr(d, U(sx(imm, 16)));
      } else if (maj == 3) {
        int op = int((p >> 22) & 15), a = int((p >> 18) & 15),
            b = int((p >> 14) & 15);
        if (op > 5)
          throw Fault("illegal branch op");
        U aa = xr(a), bb = xr(b);
        bool take = op == 0   ? aa == bb
                    : op == 1 ? aa != bb
                    : op == 2 ? sx(aa, xlen) < sx(bb, xlen)
                    : op == 3 ? sx(aa, xlen) >= sx(bb, xlen)
                    : op == 4 ? aa < bb
                              : aa >= bb;
        if (take)
          pc = pc + U(sx(p & 16383, 14) * 2);
      } else if (maj == 4) {
        int op = int((p >> 24) & 3);
        if (op > 1)
          throw Fault("illegal jump op");
        if (op == 1)
          wr(6, pc);
        pc = pc + U(sx(p & 0xffffff, 24) * 2);
      } else if (maj == 5) {
        int op = int((p >> 20) & 63), d = int((p >> 16) & 15),
            a = int((p >> 12) & 15), b = int((p >> 8) & 15);
        U aux = p & 255;
        if (op == 0) {
          if (a || b)
            throw Fault("bad csrr reserved");
          wr(d, csr_read(unsigned(aux)));
        } else if (op == 1) {
          if (d || b)
            throw Fault("bad csrw reserved");
          csr_write(unsigned(aux), xr(a));
        } else {
          if (!atomic)
            throw Fault("atomic disabled");
          if (op > 9)
            throw Fault("illegal atomic op");
          int n = op >= 6 ? 8 : 4;
          if (n == 8 && xlen != 64)
            throw Fault("64bit atomic in 32bit mode");
          if (aux)
            throw Fault("atomic reserved bits");
          U addr = xr(a);
          ram_range(addr, n, op != 2 && op != 6);
          U old = read(addr, n);
          if (op == 2 || op == 6) {
            if (b)
              throw Fault("LR reserved bits");
            wr(d, old);
            reservation = addr;
            reservation_bytes = n;
            have_reservation = true;
          } else if (op == 3 || op == 7) {
            bool good = have_reservation && reservation == addr &&
                        reservation_bytes == n;
            have_reservation = false;
            if (good)
              write(addr, xr(b), n);
            wr(d, good ? 0 : 1);
          } else {
            write(addr, (op == 4 || op == 8) ? old + xr(b) : xr(b), n);
            wr(d, old);
          }
        }
      } else if (maj == 11) {
        if (!bitops)
          throw Fault("bit manipulation extension disabled");
        int op = int((p >> 20) & 63), d = int((p >> 16) & 15),
            a = int((p >> 12) & 15), b = int((p >> 8) & 15);
        if ((p & 255) || op > 19 || ((op <= 3 || op >= 17) && b != 0))
          throw Fault("illegal bit encoding");
        wr(d, bits_alu(op, xr(a), xr(b)));
      } else if (maj == 9) {
        if (!flow)
          throw Fault("flow disabled");
        if ((p >> 24) != 0)
          throw Fault("illegal dbnz opcode");
        int d = int((p >> 20) & 15);
        if (d == 0)
          throw Fault("dbnz counter x0");
        U n = (xr(d) - 1) & xmax();
        wr(d, n);
        if (n)
          pc = pc + U(sx(p & 0xfffff, 20) * 2);
      } else if (maj == 10) {
        if (!flow)
          throw Fault("flow disabled");
        int op = int((p >> 22) & 15), d = int((p >> 18) & 15),
            b = int((p >> 14) & 15);
        if (op > 7 || b == 0 || b == d)
          throw Fault("illegal flow memory operand");
        int bytes = 1 << (op & 3);
        if (bytes == 8 && xlen != 64)
          throw Fault("64-bit flow access in XLEN32");
        U addr = xr(b);
        if (op < 4)
          wr(d, read(addr, bytes));
        else
          write(addr, xr(d), bytes);
        wr(b, addr + U(sx(p & 16383, 14)));
      } else if (maj == 6) {
        if (!simd)
          throw Fault("SIMD disabled");
        vecop(p);
      } else if (maj == 8) {
        if (xlen != 64)
          throw Fault("64-bit memory disabled");
        int op = int((p >> 22) & 15), d = int((p >> 18) & 15),
            b = int((p >> 14) & 15);
        if (op > 5)
          throw Fault("illegal 64-bit memory op");
        U addr = (xr(b) + U(sx(p & 16383, 14))) & xmax();
        int n = op <= 1 ? 8 : op <= 3 ? 4 : op == 4 ? 1 : 2;
        if (op == 1)
          write(addr, xr(d), 8);
        else {
          U z = read(addr, n);
          if (op == 2 || op == 4 || op == 5)
            z = U(sx(z, n * 8));
          wr(d, z);
        }
      } else
        throw Fault("reserved extended major");
    }
    x[0] = 0;
    pc &= xmax();
    retired++;
  }

public:
  U exit_value = 0;
  CPU(int width, size_t memory, bool tr, bool xr, bool ve, bool at, bool mul,
      bool fl, bool bits, bool trap, bool rev2)
      : ram(memory, 0), trace(tr), xreg(xr), simd(ve), atomic(at),
        multiply(mul), flow(fl), bitops(bits), traps(trap), mica2(rev2),
        xlen(width) {
    x[7] = (memory - 16) & ~size_t(15);
    csr[14] = simd;
  }
  void load(const std::vector<std::uint8_t> &code, U base = 0, U entry = 0) {
    if (base > ram.size() || code.size() > ram.size() - base)
      throw Fault("binary exceeds RAM");
    std::copy(code.begin(), code.end(), ram.begin() + std::ptrdiff_t(base));
    if ((entry & 1) || entry >= ram.size())
      throw Fault("invalid executable entry");
    pc = entry;
  }
  void set_retirement_trace(const std::string &path) {
    retirement.open(path);
    if (!retirement)
      throw Fault("cannot open retirement trace");
  }
  void set_uart_input(const std::string &bytes) {
    if (bytes.size() > 32 || bytes.size() % 2)
      throw Fault("--uart-input expects at most 16 bytes in hexadecimal");
    auto nibble = [](char c) -> unsigned {
      if (c >= '0' && c <= '9')
        return unsigned(c - '0');
      if (c >= 'a' && c <= 'f')
        return unsigned(c - 'a' + 10);
      if (c >= 'A' && c <= 'F')
        return unsigned(c - 'A' + 10);
      throw Fault("invalid hexadecimal UART input");
    };
    for (size_t i = 0; i < bytes.size(); i += 2)
      uart_input.push_back(
          std::uint8_t((nibble(bytes[i]) << 4) | nibble(bytes[i + 1])));
  }
  void set_irq(U when) {
    irq_at = when;
  }
  void emit_event(U here, U instruction, int length, bool completed,
                  bool trapped, U cause, const std::array<U, 16> &before) {
    if (!retirement.is_open())
      return;
    retirement << "{\"order\":" << event_order++ << ",\"pc\":" << here
               << ",\"insn\":" << instruction << ",\"length\":" << length
               << ",\"retired\":" << (completed ? "true" : "false")
               << ",\"next_pc\":" << pc
               << ",\"trap\":" << (trapped ? "true" : "false")
               << ",\"cause\":" << cause << ",\"regs\":[";
    for (size_t i = 0; i < x.size(); ++i)
      retirement << (i ? "," : "") << x[i];
    retirement << "],\"before\":[";
    for (size_t i = 0; i < x.size(); ++i)
      retirement << (i ? "," : "") << before[i];
    retirement << "],\"memory\":[";
    for (size_t i = 0; i < memory_events.size(); ++i) {
      const auto &e = memory_events[i];
      retirement << (i ? "," : "") << "{\"addr\":" << e.addr
                 << ",\"data\":" << e.data << ",\"bytes\":" << e.bytes
                 << ",\"write\":" << (e.write ? "true" : "false") << "}";
    }
    retirement << "]}\n";
    if (!retirement)
      throw Fault("retirement trace write failed");
  }
  void run(U limit, bool fast = false, bool native_loops = false,
           bool stop_at_budget = false) {
    for (U n = 0; n < limit; n++) {
      if (halted)
        return;
      recording = false;
      memory_events.clear();
      if (traps && retired == irq_at) {
        csr[6] |= 1;
        irq_at = ~U(0);
      }
      const U wake_pending =
          traps ? csr_read(6) : ((mica2 && retired == irq_at) ? 1u : 0u);
      const U pending = traps ? (csr[5] & wake_pending) : wake_pending;
      if (!traps && wake_pending)
        irq_at = ~U(0);
      if (sleeping) {
        if (!wake_pending) {
          ++cycles;
          ++timer;
          continue; // WFI ticks the modeled wake timer but retires nothing.
        }
        sleeping = false;
      }
      if (traps && (csr[1] & 1) && pending) {
        U here = pc;
        U cause = (U(1) << U(xlen - 1)) | ((pending & 2) ? 2 : 1);
        enter_trap(cause, here);
        emit_event(here, 0, 0, false, true, cause, x);
      }
      U here = pc, instruction = 0;
      int length = 0;
      std::array<U, 16> before{};
      if (retirement.is_open()) {
        before = x;
        if (!(pc & 1) && pc <= ram.size() && ram.size() - size_t(pc) >= 2) {
          instruction = U(ram[size_t(pc)]) | (U(ram[size_t(pc) + 1]) << 8);
          length = (instruction >> 14) == 3 ? 4 : 2;
          if (length == 4 && ram.size() - size_t(pc) >= 4)
            instruction |= U(ram[size_t(pc) + 2]) << 16 | U(ram[size_t(pc) + 3])
                                                              << 24;
        }
      }
      try {
        if (native_loops) {
          const U skipped = native_counted_loop(limit - n);
          if (skipped) {
            n += skipped - 1;
            continue;
          }
        }
        if (!fast || !fast_step()) {
          ++cycles;
          if (traps)
            ++timer;
          step();
        }
        const bool ecall = traps && instruction == (20u << 6);
        emit_event(here, instruction, length, true, ecall, ecall ? 11 : 0,
                   before);
      } catch (const Fault &e) {
        recording = false;
        pc = here;
        if (traps) {
          try {
            enter_trap(e.cause, here, e.cause == 2 ? instruction : e.value);
          } catch (const Fault &entry) {
            emit_event(here, instruction, length, false, true, e.cause, before);
            throw Fault("PC 0x" + hex(here) + ": " + e.what() +
                        "; trap entry: " + entry.what());
          }
          emit_event(here, instruction, length, false, true, e.cause, before);
        } else {
          emit_event(here, instruction, length, false, true, e.cause, before);
          throw Fault("PC 0x" + hex(here) + ": " + e.what(), e.cause, e.value);
        }
      }
    }
    if (halted || stop_at_budget)
      return;
    throw Fault("step limit exceeded");
  }
  void debugger() {
    std::set<U> breakpoints;
    std::vector<std::pair<U, U>> watchpoints;
    debug_memory = true;
    std::string line;
    while (std::cerr << "mica> " && std::getline(std::cin, line)) {
      try {
        std::istringstream in(line);
        std::string command, arg, other;
        in >> command >> arg >> other;
        auto number = [](const std::string &s) {
          size_t n = 0;
          U value = std::stoull(s, &n, 0);
          if (n != s.size())
            throw Fault("invalid debug number");
          return value;
        };
        if (command == "quit" || command == "q")
          return;
        if (command == "regs" || command == "r")
          dump();
        else if (command == "mem")
          peek(number(arg), size_t(number(other)));
        else if (command == "csr")
          std::cerr << "CSR=" << hex(csr_read(unsigned(number(arg)))) << "\n";
        else if (command == "setpc") {
          U value = number(arg);
          if ((value & 1) || value >= ram.size())
            throw Fault("invalid PC");
          pc = value;
          halted = false;
        } else if (command == "setreg") {
          U n = number(arg);
          if (n >= 16)
            throw Fault("invalid register");
          wr(int(n), number(other));
        } else if (command == "watch") {
          U address = number(arg), count = number(other);
          if (!count || address > ram.size() || count > ram.size() - address)
            throw Fault("watch outside RAM");
          watchpoints.emplace_back(address, count);
        } else if (command == "unwatch")
          watchpoints.clear();
        else if (command == "break")
          breakpoints.insert(number(arg));
        else if (command == "delete")
          breakpoints.erase(number(arg));
        else if (command == "step" || command == "s") {
          run(arg.empty() ? 1 : number(arg), false, false, true);
          dump();
        } else if (command == "continue" || command == "c") {
          for (U n = 0; n < 1000000 && !halted; n++) {
            run(1, false, false, true);
            bool watched = false;
            for (const auto &e : memory_events)
              for (const auto &[start, count] : watchpoints)
                watched = watched || (e.addr <= start + count - 1 &&
                                      start <= e.addr + U(e.bytes - 1));
            if (breakpoints.contains(pc) || watched)
              break;
          }
          dump();
        } else if (!command.empty())
          std::cerr
              << "regs | mem ADDR COUNT | csr ID | setreg N VALUE | setpc ADDR | break ADDR | delete ADDR | watch ADDR COUNT | unwatch | step [N] | continue | quit\n";
      } catch (const std::exception &e) {
        std::cerr << "debug: " << e.what() << "\n";
      }
    }
  }
  static std::string hex(U u) {
    std::ostringstream ss;
    ss << std::hex << u;
    return ss.str();
  }
  void peek(U addr, size_t count) {
    if (count > 4096 || addr >= ram.size() || count > ram.size() - addr)
      throw Fault("peek address/count outside RAM");
    std::cerr << "MEM[0x" << hex(addr) << "]=";
    for (size_t i = 0; i < count; i++)
      std::cerr << std::hex << std::setfill('0') << std::setw(2)
                << unsigned(ram[size_t(addr) + i]);
    std::cerr << std::dec << "\n";
  }
  void dump() {
    std::cerr << "pc=0x" << hex(pc) << " retired=" << std::dec << retired
              << " model_steps=" << cycles << " exit=" << exit_value << "\n";
    for (int i = 0; i < 16; i++)
      std::cerr << "x" << i << "=0x" << hex(x[size_t(i)])
                << ((i % 4 == 3) ? "\n" : " ");
  }
};
int main(int argc, char **argv) {
  try {
    std::string binary;
    int width = 32;
    size_t memory = 1024 * 1024;
    U steps = 200000;
    bool dump = true, tr = false, xr = false, v = false, a = false, m = false,
         fl = false, bits = false, trap = false, mica2 = false, fast = false,
         native_loops = false, debug = false;
    std::string peek_range, retire_path, uart_input;
    U irq_at = ~U(0);
    for (int i = 1; i < argc; i++) {
      std::string opt = argv[i];
      auto next = [&]() {
        if (i + 1 >= argc)
          throw Fault("missing argument for " + opt);
        return std::string(argv[++i]);
      };
      if (opt == "--xlen") {
        width = std::stoi(next());
        if (width != 32 && width != 64)
          throw Fault("invalid xlen");
      } else if (opt == "--retire-trace")
        retire_path = next();
      else if (opt == "--uart-input")
        uart_input = next();
      else if (opt == "--irq-at")
        irq_at = std::stoull(next(), nullptr, 0);
      else if (opt == "--memory")
        memory = std::stoull(next());
      else if (opt == "--steps")
        steps = std::stoull(next());
      else if (opt == "--peek")
        peek_range = next();
      else if (opt == "--native-loops")
        native_loops = fast = true;
      else if (opt == "--debug")
        debug = true;
      else if (opt == "--profile") {
        auto name = next();
        bool found = false;
        for (const auto &profile : mica::profiles)
          if (profile.name == name) {
            if (!profile.runnable)
              throw Fault("profile is a proposal without an implementation");
            width = profile.width;
            unsigned f = profile.features;
            xr = f & 1;
            m = f & 2;
            fl = f & 4;
            a = f & 8;
            v = f & 16;
            bits = f & 32;
            trap = f & 64;
            mica2 = f & 256;
            found = true;
          }
        if (!found)
          throw Fault("unknown processor profile: " + name);
      } else if (opt == "--fast")
        fast = true;
      else if (opt == "--trace")
        tr = true;
      else if (opt == "--quiet")
        dump = false;
      else if (opt == "--xreg")
        xr = true;
      else if (opt == "--trap")
        trap = true;
      else if (opt == "--mica2")
        mica2 = true;
      else if (opt == "--bitops")
        bits = true;
      else if (opt == "--flow")
        fl = true;
      else if (opt == "--simd")
        v = true;
      else if (opt == "--atomic")
        a = true;
      else if (opt == "--mul")
        m = true;
      else if (opt == "--version") {
        std::cout << "mica-run 2.0 development\n";
        return 0;
      } else if (opt == "--help") {
        std::cout
            << "mica-run [--mica2] [--debug] [--profile NAME] [--xlen 32|64] [--steps N] [--memory N] [--mul] [--simd] [--atomic] [--flow] [--bitops] [--trap] [--xreg] [--fast] [--native-loops] [--trace] [--retire-trace PATH] [--irq-at RETIRED] [--uart-input HEX] [--quiet] code.bin\n";
        return 0;
      } else if (opt.starts_with('-'))
        throw Fault("unknown flag: " + opt);
      else
        binary = opt;
    }
    if (binary.empty())
      throw Fault("binary file missing");
    if (memory < 4096 || memory > 512 * 1024 * 1024)
      throw Fault("memory size outside 4096..512MiB");
    if (std::filesystem::file_size(binary) > mica::elf::max_file)
      throw Fault("binary exceeds RAM");
    std::ifstream f(binary, std::ios::binary);
    if (!f)
      throw Fault("cannot read " + binary);
    std::vector<std::uint8_t> data((std::istreambuf_iterator<char>(f)),
                                   std::istreambuf_iterator<char>());
    U base = 0, entry = 0;
    if (mica::elf::is_elf(data)) {
      auto object = mica::elf::parse(data);
      if (object.type != 2)
        throw Fault("cannot execute a relocatable object; use mica-ld");
      if (int(object.width) != width)
        throw Fault("ELF XLEN differs from --xlen");
      unsigned enabled = unsigned(xr) | unsigned(m) << 1 | unsigned(fl) << 2 |
                         unsigned(a) << 3 | unsigned(v) << 4 |
                         unsigned(bits) << 5 | unsigned(trap) << 6 | 128u;
      if (object.features & ~enabled)
        throw Fault("ELF requires disabled extensions");
      base = object.base;
      entry = object.entry;
      data = std::move(object.image);
      if (entry < base || entry - base >= data.size())
        throw Fault("entry outside executable image");
    }
    CPU cpu(width, memory, tr, xr, v, a, m, fl, bits, trap, mica2);
    cpu.load(data, base, entry);
    cpu.set_uart_input(uart_input);
    if (!retire_path.empty())
      cpu.set_retirement_trace(retire_path);
    cpu.set_irq(irq_at);
    if (debug)
      cpu.debugger();
    else
      cpu.run(steps, fast, native_loops);
    if (dump)
      cpu.dump();
    if (!peek_range.empty()) {
      auto pos = peek_range.find(':');
      if (pos == std::string::npos)
        throw Fault("--peek ADDR:COUNT expected");
      U address = std::stoull(peek_range.substr(0, pos), nullptr, 0);
      size_t length = std::stoull(peek_range.substr(pos + 1), nullptr, 0);
      cpu.peek(address, length);
    }
    return cpu.exit_value ? 1 : 0;
  } catch (const std::exception &e) {
    std::cerr << "mica-run: " << e.what() << "\n";
    return 2;
  }
}
