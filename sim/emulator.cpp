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
  U pc = 0, cycles = 0, reservation = 0;
  int reservation_bytes = 0;
  bool have_reservation = false;
  U led_register = 0;
  bool halted = false, trace = false, xreg = false, simd = false,
       atomic = false, multiply = false, flow = false;
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
  void step() {
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
        halted = true;
      } else if (op == 19 || op == 22) {
        if (d || s)
          throw Fault("bad fence reserved bits");
      } else if (op == 21) {
        if (d || s)
          throw Fault("bad eret reserved bits");
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
          else
            wr(d, csr[size_t(aux)]);
        } else if (op == 1) {
          if (d || b)
            throw Fault("bad csrw reserved");
          csr[size_t(aux)] = xr(a);
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
  }

public:
  U exit_value = 0;
  CPU(int width, size_t memory, bool tr, bool xr, bool ve, bool at, bool mul,
      bool fl)
      : ram(memory, 0), trace(tr), xreg(xr), simd(ve), atomic(at),
        multiply(mul), flow(fl), xlen(width) {
    x[7] = (memory - 16) & ~size_t(15);
  }
  void load(const std::vector<std::uint8_t> &code) {
    if (code.size() > ram.size())
      throw Fault("binary exceeds RAM");
    std::copy(code.begin(), code.end(), ram.begin());
  }
  void run(U limit) {
    for (U n = 0; n < limit; n++) {
      if (halted)
        return;
      try {
        step();
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
    std::cerr << "pc=0x" << hex(pc) << " cycles=" << std::dec << cycles
              << " exit=" << exit_value << "\n";
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
         fl = false;
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
      else if (opt == "--trace")
        tr = true;
      else if (opt == "--quiet")
        dump = false;
      else if (opt == "--xreg")
        xr = true;
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
            << "mica-run [--xlen 32|64] [--steps N] [--memory N] [--mul] [--simd] [--atomic] [--flow] [--xreg] [--trace] [--quiet] code.bin\n";
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
    CPU cpu(width, memory, tr, xr, v, a, m, fl);
    cpu.load(data);
    cpu.run(steps);
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
