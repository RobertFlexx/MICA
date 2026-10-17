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
using U = std::uint64_t;
using S = std::int64_t;
using V = std::array<std::uint8_t, 16>;
struct Fault : std::runtime_error {
  using std::runtime_error::runtime_error;
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
  int reservation_bytes = 0;
  bool have_reservation = false;
  U led_register = 0;
  bool halted = false, trace = false, xreg = false, simd = false,
       atomic = false, multiply = false, flow = false, bitops = false,
       traps = false;
  int xlen = 32;
  U xmax() {
    return mask(xlen);
  }
  void checkreg(int n) {
    if (n >= 8 && !xreg)
      throw Fault("X register disabled");
  }
  U xr(int n) {
    checkreg(n);
    return n ? x[n] : 0;
  }
  void wr(int n, U value) {
    checkreg(n);
    if (n)
      x[n] = value & xmax();
  }
  U read(U addr, int n) {
    if (addr == 0xffff0008ULL)
      return cycles;
    if (addr == 0xffff000cULL)
      return 0; // functional emulator UART transmits immediately
    if (addr == 0xffff0010ULL)
      return led_register;
    if (n < 1 || n > 8 || (addr % U(n)))
      throw Fault("unaligned memory read");
    if (addr > ram.size() || U(n) > ram.size() - addr)
      throw Fault("memory read out of bounds");
    U r = 0;
    for (int i = 0; i < n; i++)
      r |= U(ram[size_t(addr) + size_t(i)]) << (8 * i);
    return r;
  }
  void write(U addr, U val, int n) {
    if (addr == 0xffff0000ULL) {
      std::cout.put(char(val & 255));
      std::cout.flush();
      return;
    }
    if (addr == 0xffff0004ULL) {
      exit_value = val & 0xffffffffULL;
      halted = true;
      return;
    }
    if (addr == 0xffff0010ULL) {
      led_register = val & 255;
      return;
    }
    if (n < 1 || n > 8 || (addr % U(n)))
      throw Fault("unaligned memory write");
    if (addr > ram.size() || U(n) > ram.size() - addr)
      throw Fault("memory write out of bounds");
    for (int i = 0; i < n; i++)
      ram[size_t(addr) + size_t(i)] = std::uint8_t(val >> (8 * i));
    // An actual shared-memory system requires every write by every hart to invalidate reservations.
    if (have_reservation && addr < reservation + U(reservation_bytes) &&
        reservation < addr + U(n))
      have_reservation = false;
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
  static U sat(__int128 n, int bits, bool sign) {
    __int128 lo = sign ? -((__int128)1 << (bits - 1)) : 0;
    __int128 hi = sign         ? (((__int128)1 << (bits - 1)) - 1)
                  : bits == 64 ? (__int128)std::numeric_limits<U>::max()
                               : (((__int128)1 << bits) - 1);
    if (n < lo)
      n = lo;
    if (n > hi)
      n = hi;
    return U(n) & mask(bits);
  }
  static U satu(unsigned __int128 n, int bits) {
    unsigned __int128 limit =
        bits == 64 ? (unsigned __int128)std::numeric_limits<U>::max()
                   : (((unsigned __int128)1 << bits) - 1);
    return U(n > limit ? limit : n);
  }
  static U shift_round(U a, int shift, int bits, bool sign) {
    if (!shift)
      return a;
    // Quotient toward negative infinity, then nearest-even rounding.
    __int128 n = sign ? (__int128)sx(a, bits) : (__int128)(a & mask(bits));
    __int128 q = n >> shift;
    __int128 rem = n - (q << shift);
    __int128 half = (__int128)1 << (shift - 1);
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
      return ((a >> shift) | (a << ((xlen - shift) & (xlen - 1)))) & xmax();
    case 5:
      return ((a << shift) | (a >> ((xlen - shift) & (xlen - 1)))) & xmax();
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
        throw Fault("misaligned vector address");
      if (op == 16) {
        for (int k = 0; k < 16; k++)
          v[d][size_t(k)] = std::uint8_t(read(addr + U(k), 1));
      } else
        for (int k = 0; k < 16; k++)
          write(addr + U(k), v[d][size_t(k)], 1);
      return;
    }
    if ((saturate && op > 2) || (round && op != 7 && op != 8) ||
        (op == 15 && bits != 8))
      throw Fault("illegal vector modifier");
    V dst{};
    for (int i = 0; i < n; i++) {
      U va = laneslot(v[a], i, bytes), vb = laneslot(v[b], i, bytes), r = 0;
      __int128 aa = sign ? (__int128)sx(va, bits) : (__int128)va;
      __int128 bb = sign ? (__int128)sx(vb, bits) : (__int128)vb;
      int sh = int(vb & U(bits - 1));
      switch (op) {
      case 0:
        r = saturate ? sat(aa + bb, bits, sign) : U(va + vb);
        break;
      case 1:
        r = saturate ? sat(aa - bb, bits, sign) : U(va - vb);
        break;
      case 2:
        r = saturate
                ? (sign ? sat(aa * bb, bits, true)
                        : satu((unsigned __int128)va * (unsigned __int128)vb,
                               bits))
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
        __int128 dot = 0;
        for (int j = 0; j < 4; j++) {
          U lv = laneslot(v[a], i * 4 + j, 1),
            rv = laneslot(v[b], i * 4 + j, 1);
          dot += (sign ? (__int128)sx(lv, 8) : (__int128)lv) *
                 (sign ? (__int128)sx(rv, 8) : (__int128)rv);
        }
        r = U(dot);
        break;
      }
      case 18:
      case 19: {
        int src = i / 2 + (op == 19 ? n / 2 : 0);
        r = laneslot((i & 1) ? v[b] : v[a], src, bytes);
        break;
      }
      case 20:
      case 21: {
        int src = (i % (n / 2)) * 2 + (op == 21 ? 1 : 0);
        r = laneslot(i < n / 2 ? v[a] : v[b], src, bytes);
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
    v[d] = dst;
  }
  // Translate one very common two-instruction counted loop to a native loop.
  // This is NOT a whole-program JIT. Memory, traps, tracing and exotic loops
  // still use the reference engine. Volatile state forces actual iteration,
  // instead of replacing a benchmark with a multiplication and calling it fast.
  U native_counted_loop(U step_budget) {
    if (traps || trace || !flow || pc > ram.size() ||
        ram.size() - size_t(pc) < 6 || (pc & 1)) return 0;
    const size_t ip = size_t(pc);
    const unsigned hw = unsigned(ram[ip]) | (unsigned(ram[ip + 1]) << 8);
    if ((hw >> 14) != 1 || ((hw >> 11) & 7) != 1) return 0; // addi
    const unsigned d = (hw >> 8) & 7;
    if (d == 0) return 0;
    const unsigned bh = unsigned(ram[ip + 2]) | (unsigned(ram[ip + 3]) << 8);
    if ((bh >> 14) != 3 || ((bh >> 10) & 15) != 9) return 0;
    const U payload = (U(bh & 1023) << 16) | U(ram[ip + 4]) |
                      (U(ram[ip + 5]) << 8);
    const unsigned c = unsigned((payload >> 20) & 15);
    if (c == 0 || c == d || (c >= 8 && !xreg) || (payload >> 24) ||
        sx(payload & 0xfffff, 20) != -3) return 0;
    const U count = x[c] & xmax();
    if (count == 0 || count > step_budget / 2) return 0;
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
    if (traps || trace || pc > ram.size() || ram.size() - size_t(pc) < 2 || (pc & 1))
      return false;
    const size_t ip = size_t(pc);
    const unsigned hw = unsigned(ram[ip]) | (unsigned(ram[ip + 1]) << 8);
    const unsigned klass = hw >> 14;
    U next = (pc + 2) & xmax();
    if (klass == 1) {
      const unsigned op = (hw >> 11) & 7, d = (hw >> 8) & 7;
      const U imm = hw & 255u;
      switch (op) {
      case 0: x[d] = U(sx(imm, 8)) & xmax(); break;
      case 1: x[d] = (x[d] + U(sx(imm, 8))) & xmax(); break;
      case 2: x[d] &= imm; break;
      case 3: if (imm > 31) return false; x[d] = (x[d] << imm) & xmax(); break;
      case 4: if (imm > 31) return false; x[d] >>= imm; break;
      case 5: if (!x[d]) next = (next + U(sx(imm, 8) * 2)) & xmax(); break;
      case 6: if (x[d]) next = (next + U(sx(imm, 8) * 2)) & xmax(); break;
      case 7: next = (next + U(sx(hw & 2047u, 11) * 2)) & xmax(); break;
      }
      // x0 is architecturally zero, even for short immediate instructions.
      x[0] = 0;
    } else if (klass == 0) {
      const unsigned op = (hw >> 6) & 255u, d = (hw >> 3) & 7, a = hw & 7;
      switch (op) {
      case 0: if (d || a) return false; break;
      case 1: x[d] = x[a]; break;
      case 2: x[d] = (x[d] + x[a]) & xmax(); break;
      case 3: x[d] = (x[d] - x[a]) & xmax(); break;
      case 4: x[d] &= x[a]; break;
      case 5: x[d] |= x[a]; break;
      case 6: x[d] ^= x[a]; break;
      case 7: x[d] = (x[d] << (x[a] & (xlen - 1))) & xmax(); break;
      case 8: x[d] >>= (x[a] & (xlen - 1)); break;
      case 9: x[d] = ash(x[d], int(x[a] & (xlen - 1)), xlen); break;
      case 10: x[d] = sx(x[d], xlen) < sx(x[a], xlen); break;
      case 11: x[d] = x[d] < x[a]; break;
      case 12: x[d] = x[d] == x[a]; break;
      case 13: if (a) return false; next = x[d] & xmax(); break;
      case 14: if (a) return false; next = x[d] & xmax(); x[6] = (pc + 2) & xmax(); break;
      case 15: if (a) return false; x[d] = ~x[d] & xmax(); break;
      case 16: if (a) return false; x[d] = -x[d] & xmax(); break;
      case 17: if (!multiply) return false; x[d] = x[d] * x[a] & xmax(); break;
      case 18: if (d || a) return false; halted = true; break;
      case 19: case 22: if (d || a) return false; break;
      case 20: if (d || a) return false; halted = true; break;
      default: return false;
      }
      x[0] = 0;
    } else if (klass == 3 && flow && ip + 4 <= ram.size()) {
      const unsigned major = (hw >> 10) & 15;
      if (major != 9) return false;
      const U payload = U(hw & 1023u) << 16 | U(ram[ip + 2]) | (U(ram[ip + 3]) << 8);
      if ((payload >> 24) || ((payload >> 20) & 15u) == 0) return false;
      const unsigned d = unsigned(payload >> 20) & 15u;
      if (d >= 8 && !xreg) return false;
      x[d] = (x[d] - 1) & xmax();
      next = (pc + 4) & xmax();
      if (x[d]) next = (next + U(sx(payload & 0xfffffu, 20) * 2)) & xmax();
    } else return false;
    pc = next;
    ++cycles;
    ++retired;
    return true;
  }
  void enter_trap(U cause, U saved_pc) {
    if ((csr[4] & 1) || csr[4] == 0 || csr[4] >= ram.size())
      throw Fault("invalid trap vector");
    if (csr[1] & 4)
      throw Fault("double trap without handler stack");
    csr[2] = saved_pc & xmax();
    csr[3] = cause & xmax();
    csr[1] = (csr[1] & ~U(7)) | ((csr[1] & 1) ? U(2) : U(0)) | 4;
    pc = csr[4];
    have_reservation = false;
  }
  void step() {
    if (traps && (csr[1] & 1) && (csr[5] & (csr[6] | U(0)) & 1))
      enter_trap((U(1) << (xlen - 1)) | 1, pc);

    if (pc % 2 || pc + 2 > ram.size())
      throw Fault("invalid fetch alignment/range");
    U here = pc;
    U hw = read(pc, 2), klass = hw >> 14;
    int size = klass == 3 ? 4 : 2;
    if (pc + U(size) > ram.size())
      throw Fault("truncated 32-bit instruction");
    U p = klass == 3 ? (((hw & 1023) << 16) | read(pc + 2, 2)) : 0;
    pc += U(size);
    cycles++;
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
          enter_trap(11, pc);
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
        pc = U(S(pc) + sx(off, 11) * 2);
      } else if (op == 5 || op == 6) {
        if ((xr(d) == 0) == (op == 5))
          pc = U(S(pc) + sx(imm, 8) * 2);
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
      U addr = xr(b) + U(off);
      int n = op == 0 || op == 1 ? 4 : op == 2 || op == 3 || op == 6 ? 2 : 1;
      if (op == 1 || op == 3 || op == 5)
        write(addr, xr(d), n);
      else {
        U z = read(addr, n);
        if (op == 2 || op == 4)
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
        if (op > 2)
          throw Fault("illegal wide opcode");
        if (op == 0)
          wr(d, imm << 16);
        else if (op == 1)
          wr(d, (xr(d) & ~U(65535)) | imm);
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
          pc = U(S(pc) + sx(p & 16383, 14) * 2);
      } else if (maj == 4) {
        int op = int((p >> 24) & 3);
        if (op > 1)
          throw Fault("illegal jump op");
        if (op == 1)
          wr(6, pc);
        pc = U(S(pc) + sx(p & 0xffffff, 24) * 2);
      } else if (maj == 5) {
        int op = int((p >> 20) & 63), d = int((p >> 16) & 15),
            a = int((p >> 12) & 15), b = int((p >> 8) & 15);
        U aux = p & 255;
        if (op == 0) {
          if (a || b)
            throw Fault("bad csrr reserved");
          if (aux == 7)
            wr(d, cycles & 0xffffffff);
          else if (aux == 8)
            wr(d, cycles >> 32);
          else if (aux == 15)
            wr(d, U(xreg) | U(multiply) << 1 | U(flow) << 2 | U(atomic) << 3 |
                      U(simd) << 4 | U(bitops) << 5 | U(traps) << 6 |
                      U(1) << 7);
          else if (aux == 16)
            wr(d, U(xlen));
          else if (aux == 17)
            wr(d, retired & 0xffffffffULL);
          else if (aux == 18)
            wr(d, retired >> 32);
          else
            wr(d, csr[size_t(aux)]);
        } else if (op == 1) {
          if (d || b)
            throw Fault("bad csrw reserved");
          if (aux == 0 || aux == 7 || aux == 8 || aux == 15 || aux == 16 ||
              aux == 17 || aux == 18)
            throw Fault("CSR is read-only");
          if (traps && aux == 1)
            csr[1] = (csr[1] & ~U(1)) | (xr(a) & 1);
          else
            csr[size_t(aux)] = xr(a) & xmax();
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
          U old = read(addr, n);
          if (op == 2 || op == 6) {
            if (b)
              throw Fault("LR reserved bits");
            wr(d, old);
            reservation = addr;
            reservation_bytes = n;
            have_reservation = true;
          } else if (op == 3 || op == 7) {
            bool good = have_reservation && reservation == addr;
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
          pc = U(S(pc) + sx(p & 0xfffff, 20) * 2);
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
        U addr = xr(b) + U(sx(p & 16383, 14));
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
      bool fl, bool bits, bool trap)
      : ram(memory, 0), trace(tr), xreg(xr), simd(ve), atomic(at),
        multiply(mul), flow(fl), bitops(bits), traps(trap), xlen(width) {
    x[7] = (memory - 16) & ~size_t(15);
  }
  void load(const std::vector<std::uint8_t> &code) {
    if (code.size() > ram.size())
      throw Fault("binary exceeds RAM");
    std::copy(code.begin(), code.end(), ram.begin());
  }
  void run(U limit, bool fast = false, bool native_loops = false) {
    for (U n = 0; n < limit; n++) {
      if (halted)
        return;
      try {
        if (native_loops) {
          const U skipped = native_counted_loop(limit - n);
          if (skipped) { n += skipped - 1; continue; }
        }
        if (!fast || !fast_step()) step();
      } catch (const Fault &e) {
        throw Fault("PC 0x" + hex(pc) + ": " + e.what());
      }
    }
    throw Fault("step limit exceeded");
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
         fl = false, bits = false, trap = false, fast = false, native_loops = false;
    std::string peek_range;
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
      } else if (opt == "--memory")
        memory = std::stoull(next());
      else if (opt == "--steps")
        steps = std::stoull(next());
      else if (opt == "--peek")
        peek_range = next();
      else if (opt == "--native-loops")
        native_loops = fast = true;
      else if (opt == "--fast")
        fast = true;
      else if (opt == "--trace")
        tr = true;
      else if (opt == "--quiet")
        dump = false;
      else if (opt == "--xreg")
        xr = true;
      else if (opt == "--trap")
        trap = true;
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
      else if (opt == "--help") {
        std::cout
            << "mica-run [--xlen 32|64] [--steps N] [--memory N] [--mul] [--simd] [--atomic] [--flow] [--bitops] [--trap] [--xreg] [--fast] [--native-loops] [--trace] [--quiet] code.bin\n";
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
    std::ifstream f(binary, std::ios::binary);
    if (!f)
      throw Fault("cannot read " + binary);
    std::vector<std::uint8_t> data((std::istreambuf_iterator<char>(f)),
                                   std::istreambuf_iterator<char>());
    CPU cpu(width, memory, tr, xr, v, a, m, fl, bits, trap);
    cpu.load(data);
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
