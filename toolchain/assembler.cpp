// MICA-32/64 v1.0: standalone, dependency-free, two-pass C++23 assembler.
// SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>
namespace fs = std::filesystem;
using U = std::uint64_t;
using S = std::int64_t;
using Bytes = std::vector<std::uint8_t>;
struct Error : std::runtime_error {
  using std::runtime_error::runtime_error;
};
static std::string trim(std::string s) {
  auto a = s.find_first_not_of(" \r\t\n");
  if (a == s.npos)
    return "";
  auto z = s.find_last_not_of(" \r\t\n");
  return s.substr(a, z - a + 1);
}
static std::string lower(std::string s) {
  for (auto &c : s)
    c = char(std::tolower(static_cast<unsigned char>(c)));
  return s;
}
static std::string clean(const std::string &s) {
  bool quote = false, esc = false;
  for (size_t i = 0; i < s.size(); i++) {
    char c = s[i];
    if (quote) {
      if (esc)
        esc = false;
      else if (c == '\\')
        esc = true;
      else if (c == '"')
        quote = false;
    } else if (c == '"')
      quote = true;
    else if (c == ';' || (c == '/' && i + 1 < s.size() && s[i + 1] == '/'))
      return trim(s.substr(0, i));
  }
  return trim(s);
}
static std::vector<std::string> split(const std::string &s) {
  std::vector<std::string> out;
  std::string cur;
  int brackets = 0;
  bool quote = false, esc = false;
  for (char c : s) {
    if (quote) {
      cur += c;
      if (esc)
        esc = false;
      else if (c == '\\')
        esc = true;
      else if (c == '"')
        quote = false;
      continue;
    }
    if (c == '"') {
      quote = true;
      cur += c;
      continue;
    }
    if (c == '[')
      brackets++;
    if (c == ']')
      brackets--;
    if (brackets < 0)
      throw Error("unbalanced ]");
    if (c == ',' && brackets == 0) {
      out.push_back(trim(cur));
      cur.clear();
    } else
      cur += c;
  }
  if (quote || brackets)
    throw Error("unclosed string or bracket");
  if (!trim(cur).empty())
    out.push_back(trim(cur));
  for (auto &a : out)
    if (a.empty())
      throw Error("empty operand");
  return out;
}
static void append(Bytes &v, U n, int size) {
  for (int i = 0; i < size; i++)
    v.push_back(static_cast<std::uint8_t>(n >> (8 * i)));
}
static std::string replace_word(std::string s, const std::string &from,
                                const std::string &to) {
  size_t p = 0;
  while ((p = s.find(from, p)) != std::string::npos) {
    auto word = [](char c) {
      return std::isalnum(static_cast<unsigned char>(c)) || c == '_' ||
             c == '.' || c == '$';
    };
    if ((p == 0 || !word(s[p - 1])) &&
        (p + from.size() == s.size() || !word(s[p + from.size()]))) {
      s.replace(p, from.size(), to);
      p += to.size();
    } else
      p += from.size();
  }
  return s;
}
using Symbols = std::unordered_map<std::string, U>;
class Expression {
  std::string s;
  size_t p = 0;
  const Symbols &sym;
  bool unknown_ok;
  void ws() {
    while (p < s.size() && std::isspace(static_cast<unsigned char>(s[p])))
      p++;
  }
  bool eat(std::string_view t) {
    ws();
    if (s.substr(p, t.size()) == t) {
      p += t.size();
      return true;
    }
    return false;
  }
  U atom() {
    ws();
    if (eat("(")) {
      U v = expr(0);
      if (!eat(")"))
        throw Error("expected ) in expression");
      return v;
    }
    if (eat("+"))
      return atom();
    if (eat("-"))
      return U(0) - atom();
    if (eat("~"))
      return ~atom();
    if (p >= s.size())
      throw Error("incomplete expression");
    if (std::isdigit(static_cast<unsigned char>(s[p]))) {
      size_t start = p;
      int base = 10;
      if (p + 1 < s.size() && s[p] == '0' &&
          (s[p + 1] == 'x' || s[p + 1] == 'X' || s[p + 1] == 'b' ||
           s[p + 1] == 'B')) {
        base = (s[p + 1] == 'x' || s[p + 1] == 'X') ? 16 : 2;
        p += 2;
      } else if (s[p] == '0' && p + 1 < s.size() &&
                 std::isdigit(static_cast<unsigned char>(s[p + 1])))
        base = 10;
      auto ds = p;
      while (p < s.size() && std::isalnum(static_cast<unsigned char>(s[p])))
        p++;
      if (ds == p)
        throw Error("invalid number: " + s.substr(start, p - start));
      U v = 0;
      auto result = std::from_chars(s.data() + ds, s.data() + p, v, base);
      if (result.ec != std::errc{} || result.ptr != s.data() + p)
        throw Error("invalid/overflowed number: " + s.substr(start, p - start));
      return v;
    }
    if (std::isalpha(static_cast<unsigned char>(s[p])) || s[p] == '_' ||
        s[p] == '.' || s[p] == '$') {
      size_t a = p++;
      while (p < s.size() && (std::isalnum(static_cast<unsigned char>(s[p])) ||
                              s[p] == '_' || s[p] == '.' || s[p] == '$'))
        p++;
      auto name = s.substr(a, p - a);
      auto it = sym.find(name);
      if (it == sym.end()) {
        if (unknown_ok)
          return 0;
        throw Error("undefined symbol: " + name);
      }
      return it->second;
    }
    throw Error("unexpected character in expression: " + s.substr(p));
  }
  static int prec(std::string_view v) {
    if (v == "|")
      return 1;
    if (v == "^")
      return 2;
    if (v == "&")
      return 3;
    if (v == "<<" || v == ">>")
      return 4;
    if (v == "+" || v == "-")
      return 5;
    if (v == "*" || v == "/" || v == "%")
      return 6;
    return 0;
  }
  U expr(int minp) {
    U lhs = atom();
    while (true) {
      ws();
      std::string op;
      for (auto t : {"<<", ">>", "+", "-", "*", "/", "%", "&", "^", "|"})
        if (s.substr(p, std::char_traits<char>::length(t)) == t) {
          op = t;
          break;
        }
      int pr = prec(op);
      if (!pr || pr < minp)
        break;
      p += op.size();
      U rhs = expr(pr + 1);
      if (op == "+")
        lhs += rhs;
      else if (op == "-")
        lhs -= rhs;
      else if (op == "*")
        lhs *= rhs;
      else if (op == "/") {
        if (!rhs)
          throw Error("division by zero");
        lhs /= rhs;
      } else if (op == "%") {
        if (!rhs)
          throw Error("modulo by zero");
        lhs %= rhs;
      } else if (op == "<<") {
        if (rhs >= 64)
          throw Error("oversized shift");
        lhs <<= rhs;
      } else if (op == ">>") {
        if (rhs >= 64)
          throw Error("oversized shift");
        lhs >>= rhs;
      } else if (op == "&")
        lhs &= rhs;
      else if (op == "^")
        lhs ^= rhs;
      else
        lhs |= rhs;
    }
    return lhs;
  }

public:
  Expression(std::string str, const Symbols &symbols, bool unknown)
      : s(std::move(str)), sym(symbols), unknown_ok(unknown) {}
  U get() {
    auto n = expr(0);
    ws();
    if (p != s.size())
      throw Error("invalid expression tail: " + s.substr(p));
    return n;
  }
};
static U val(const std::string &s, const Symbols &sy, bool sizing) {
  return Expression(s, sy, sizing).get();
}
static U mask(int bits) {
  return bits == 64 ? ~U(0) : (U(1) << bits) - 1;
}
static U range(U n, int bits, bool sign, const std::string &what) {
  S x = std::bit_cast<S>(n);
  if (sign) {
    if (bits < 64 &&
        (x < -(S(1) << (bits - 1)) || x > ((S(1) << (bits - 1)) - 1)))
      throw Error(what + " out of signed " + std::to_string(bits) +
                  "-bit range");
  } else if (bits < 64 && n > mask(bits))
    throw Error(what + " out of unsigned " + std::to_string(bits) +
                "-bit range");
  return n & mask(bits);
}
static U rel(U target, U pc, int bytes, int bits) {
  S delta = std::bit_cast<S>(target - (pc + U(bytes)));
  if (delta & 1)
    throw Error("branch target not 2-byte aligned");
  return range(std::bit_cast<U>(delta / 2), bits, true, "relative branch");
}
static int reg(const std::string &name, bool ext, bool vec = false) {
  auto x = lower(trim(name));
  if (vec) {
    if (x.size() == 2 && x[0] == 'v' && x[1] >= '0' && x[1] <= '7')
      return x[1] - '0';
    throw Error("expected v0..v7, got " + name);
  }
  const std::unordered_map<std::string, int> aliases = {
      {"zero", 0}, {"a0", 1}, {"a1", 2}, {"a2", 3}, {"a3", 4},
      {"t0", 5},   {"fp", 5}, {"lr", 6}, {"sp", 7}};
  int n = -1;
  auto it = aliases.find(x);
  if (it != aliases.end())
    n = it->second;
  else if (x.size() >= 2 && x[0] == 'x' && x.size() <= 3) {
    auto [ptr, ec] = std::from_chars(x.data() + 1, x.data() + x.size(), n);
    if (ec != std::errc{} || ptr != x.data() + x.size())
      n = -1;
  }
  if (n < 0 || n > 15 || (n >= 8 && !ext))
    throw Error("bad register / X disabled: " + name);
  return n;
}
static std::pair<int, U> mem(const std::string &arg, const Symbols &sy,
                             bool sizing, bool ext) {
  auto t = trim(arg);
  if (t.size() < 3 || t.front() != '[' || t.back() != ']')
    throw Error("expected [base +/- byte_offset]");
  t = trim(t.substr(1, t.size() - 2));
  auto delim = t.find_first_of("+-");
  std::string base = trim(t.substr(0, delim));
  U offset = delim == std::string::npos ? 0 : val(t.substr(delim), sy, sizing);
  return {reg(base, ext), offset};
}
static Bytes r16(int op, int d = 0, int s = 0) {
  Bytes b;
  append(b, U((op << 6) | (d << 3) | s), 2);
  return b;
}
static Bytes i16(int op, int d, U imm) {
  Bytes b;
  append(b, 0x4000U | U(op << 11) | U(d << 8) | (imm & 255), 2);
  return b;
}
static Bytes m16(int op, int d, int base, U off) {
  Bytes b;
  append(b, 0x8000U | U(op << 11) | U(d << 8) | U(base << 5) | (off & 31), 2);
  return b;
}
static Bytes e32(int maj, U payload) {
  Bytes b;
  append(b, 0xc000U | U(maj << 10) | ((payload >> 16) & 1023), 2);
  append(b, payload & 65535, 2);
  return b;
}
static Bytes alu3(int major, int op, int d, int a, int b) {
  return e32(major, U(op << 20) | U(d << 16) | U(a << 12) | U(b << 8));
}
static Bytes wide(int op, int rd, U imm) {
  return e32(2, U(op << 20) | U(rd << 16) | (imm & 65535));
}
static void join(Bytes &to, const Bytes &src) {
  to.insert(to.end(), src.begin(), src.end());
}
static const std::map<std::string, int> R = {
    {"nop", 0},    {"mov", 1},   {"add", 2},     {"sub", 3},  {"and", 4},
    {"or", 5},     {"xor", 6},   {"shl", 7},     {"shr", 8},  {"sar", 9},
    {"slt", 10},   {"sltu", 11}, {"seq", 12},    {"jr", 13},  {"jalr", 14},
    {"not", 15},   {"neg", 16},  {"mul", 17},    {"wfi", 18}, {"fence", 19},
    {"ecall", 20}, {"eret", 21}, {"fence.i", 22}};
static const std::map<std::string, int> I = {
    {"li8", 0},  {"addi", 1}, {"andi", 2}, {"shli", 3},
    {"shri", 4}, {"bz", 5},   {"bnz", 6},  {"b", 7}};
static const std::map<std::string, std::pair<int, int>> MEM = {
    {"ldw", {0, 4}}, {"stw", {1, 4}}, {"ldh", {2, 2}},  {"sth", {3, 2}},
    {"ldb", {4, 1}}, {"stb", {5, 1}}, {"ldhu", {6, 2}}, {"ldbu", {7, 1}}};
static const std::map<std::string, int> ALU = {
    {"add3", 0}, {"sub3", 1},  {"and3", 2},  {"or3", 3},
    {"xor3", 4}, {"shl3", 5},  {"shr3", 6},  {"sar3", 7},
    {"slt3", 8}, {"sltu3", 9}, {"seq3", 10}, {"mul3", 11}};
static const std::map<std::string, int> IMM = {
    {"add3i", 0}, {"and3i", 1}, {"or3i", 2}, {"xor3i", 3},
    {"shl3i", 4}, {"shr3i", 5}, {"sar3i", 6}};
static const std::map<std::string, int> WIDE = {
    {"movhi", 0}, {"movlo", 1}, {"li16", 2}};
static const std::map<std::string, int> BR = {
    {"beq", 0}, {"bne", 1}, {"blt", 2}, {"bge", 3}, {"bltu", 4}, {"bgeu", 5}};
static const std::map<std::string, int> SYS = {
    {"csrr", 0},     {"csrw", 1},      {"lr.w", 2}, {"sc.w", 3},
    {"amoadd.w", 4}, {"amoswap.w", 5}, {"lr.q", 6}, {"sc.q", 7},
    {"amoadd.q", 8}, {"amoswap.q", 9}};
static const std::map<std::string, int> BITOPS = {
    {"clz3", 0},   {"ctz3", 1},    {"popcnt3", 2}, {"rev8", 3},
    {"ror3", 4},   {"rol3", 5},    {"min3", 6},    {"max3", 7},
    {"minu3", 8},  {"maxu3", 9},   {"bset3", 10},  {"bclr3", 11},
    {"binv3", 12}, {"bext3", 13},  {"andn3", 14},  {"orn3", 15},
    {"xnor3", 16}, {"sextb3", 17}, {"sexth3", 18}, {"zexth3", 19}};
static const std::map<std::string, int> W32 = {
    {"addw3", 0}, {"subw3", 1}, {"shlw3", 2}, {"shrw3", 3}, {"sarw3", 4},
    {"andw3", 5}, {"orw3", 6},  {"xorw3", 7}, {"mulw3", 8}};
static const std::map<std::string, int> FLOW = {
    {"ldpi.b", 0}, {"ldpi.h", 1}, {"ldpi.w", 2}, {"ldpi.q", 3},
    {"stpi.b", 4}, {"stpi.h", 5}, {"stpi.w", 6}, {"stpi.q", 7}};
static const std::map<std::string, int> MX = {
    {"ldq", 0}, {"stq", 1}, {"ldws", 2}, {"ldwu", 3}, {"ldbs", 4}, {"ldhs", 5}};
static const std::map<std::string, int> V = {
    {"vadd", 0},      {"vsub", 1},     {"vmul", 2},    {"vand", 3},
    {"vor", 4},       {"vxor", 5},     {"vshl", 6},    {"vshr", 7},
    {"vsar", 8},      {"vmin", 9},     {"vmax", 10},   {"vcmpeq", 11},
    {"vcmplt", 12},   {"vabs", 13},    {"vneg", 14},   {"vdot8", 15},
    {"vld", 16},      {"vst", 17},     {"vziplo", 18}, {"vziphi", 19},
    {"vunziplo", 20}, {"vunziphi", 21}};
static const std::map<std::string, int> CSRS = {
    {"coreid", 0},   {"status", 1},      {"epc", 2},          {"cause", 3},
    {"tvec", 4},     {"ie", 5},          {"ip", 6},           {"cycle_lo", 7},
    {"cycle_hi", 8}, {"timer_lo", 9},    {"timer_hi", 10},    {"cmp_lo", 11},
    {"cmp_hi", 12},  {"vec_dirty", 13},  {"vec_enabled", 14}, {"features", 15},
    {"arch", 16},    {"instret_lo", 17}, {"instret_hi", 18}};
struct Src {
  std::string filename, text;
  int line = 0;
};
struct Line {
  Src src;
  std::string label, op;
  std::vector<std::string> a;
  U pc = 0;
  size_t size = 0;
};
struct Macro {
  std::vector<std::string> params;
  std::vector<Src> body;
};
class Assembler {
  int xlen = 32;
  bool xreg = false, simd = false, atomic = false, multiply = false,
       flow = false, bitops = false;
  U unique = 0;
  size_t expanded_lines = 0;
  std::vector<fs::path> include_stack;
  std::map<std::string, Macro> macros;
  std::vector<Line> lines;
  Symbols sy;
  static std::string word(const std::string &text) {
    auto s = clean(text);
    auto space = s.find_first_of(" \t");
    return lower(s.substr(0, space));
  }
  std::vector<Src> read(const fs::path &path, int depth) {
    if (depth > 12)
      throw Error(".include depth exceeds 12");
    std::ifstream f(path);
    if (!f)
      throw Error("cannot open " + path.string());
    std::vector<Src> v;
    std::string s;
    int n = 0;
    while (std::getline(f, s)) {
      v.push_back({path.string(), s, ++n});
      if (v.size() > 100000)
        throw Error("source too large");
    }
    return v;
  }
  std::vector<Src> expand(const std::vector<Src> &input, int depth) {
    if (depth > 24)
      throw Error("macro/repeat nesting too deep");
    std::vector<Src> out;
    for (size_t i = 0; i < input.size(); i++) {
      if (++expanded_lines > 200000)
        throw Error("expanded source exceeds 200000 lines");
      const auto &src = input[i];
      auto stripped = clean(src.text), w = word(src.text);
      if (w.empty()) {
        out.push_back(src);
        continue;
      }
      if (w == ".include") {
        auto arg = trim(stripped.substr(8));
        if (arg.size() < 2 || arg.front() != '"' || arg.back() != '"')
          throw Error(".include expects quoted relative path");
        auto path = fs::weakly_canonical(fs::path(src.filename).parent_path() /
                    arg.substr(1, arg.size() - 2));
        if (std::find(include_stack.begin(), include_stack.end(), path) != include_stack.end())
          throw Error("recursive include: " + path.string());
        include_stack.push_back(path);
        auto part = expand(read(path, depth + 1), depth + 1);
        include_stack.pop_back();
        out.insert(out.end(), part.begin(), part.end());
        continue;
      }
      if (w == ".macro" || w == ".repeat") {
        std::vector<Src> body;
        int nest = 1;
        auto closing = w == ".macro" ? ".endm" : ".endrepeat";
        while (++i < input.size()) {
          auto w2 = word(input[i].text);
          if (w2 == w)
            nest++;
          if (w2 == closing && --nest == 0)
            break;
          if (w2 != closing) {
            if (w2 != w) {
            }
          } // preserve original source lines and nested directives
          body.push_back(input[i]);
        }
        if (i == input.size())
          throw Error("unterminated " + w);
        if (w == ".macro") {
          auto tokens = trim(stripped.substr(6));
          auto sp = tokens.find_first_of(" \t,");
          auto name = lower(tokens.substr(0, sp));
          if (name.empty() || macros.contains(name))
            throw Error("invalid or duplicate macro: " + name);
          auto params = sp == tokens.npos ? std::vector<std::string>{}
                                          : split(trim(tokens.substr(sp + 1)));
          macros[name] = {params, body};
        } else {
          U count = val(trim(stripped.substr(7)), sy, false);
          if (count > 1024)
            throw Error(".repeat exceeds 1024");
          for (U n = 0; n < count; n++) {
            auto portion = body;
            for (auto &s : portion)
              s.text = replace_word(s.text, "$index", std::to_string(n));
            auto part = expand(portion, depth + 1);
            out.insert(out.end(), part.begin(), part.end());
          }
        }
        continue;
      }
      if (w == ".endm" || w == ".endrepeat")
        throw Error("unmatched " + w);
      if (auto m = macros.find(w); m != macros.end()) {
        auto args = split(trim(stripped.substr(w.size())));
        if (args.size() != m->second.params.size())
          throw Error("macro " + w + " wrong argument count");
        auto body = m->second.body;
        const std::string id = "__m" + std::to_string(++unique) + "_";
        for (auto &b : body) {
          b.text = std::regex_replace(
              b.text, std::regex("%%([A-Za-z_][A-Za-z0-9_]*)"), id + "$1");
          for (size_t p = 0; p < args.size(); p++)
            b.text = replace_word(b.text, "$" + m->second.params[p], args[p]);
        }
        auto part = expand(body, depth + 1);
        out.insert(out.end(), part.begin(), part.end());
        continue;
      }
      out.push_back(src);
      if (out.size() > 150000)
        throw Error("expansion exceeds 150000 lines");
    }
    return out;
  }
  void parse(const std::vector<Src> &src) {
    const std::regex label(R"(^([A-Za-z_.$][A-Za-z0-9_.$]*):\s*)");
    for (auto &s : src) {
      auto t = clean(s.text);
      if (t.empty())
        continue;
      Line l;
      l.src = s;
      std::smatch match;
      if (std::regex_search(t, match, label)) {
        l.label = match[1];
        t = trim(t.substr(match.length()));
      }
      if (!t.empty()) {
        auto sp = t.find_first_of(" \t");
        l.op = lower(t.substr(0, sp));
        if (sp != t.npos)
          l.a = split(trim(t.substr(sp + 1)));
      }
      lines.push_back(std::move(l));
    }
  }
  static void nargs(const Line &l, size_t n) {
    if (l.a.size() != n)
      throw Error(l.op + " expects " + std::to_string(n) + " operands");
  }
  U num(const std::string &s, bool sizing) {
    return val(s, sy, sizing);
  }
  Bytes enc(Line &l, bool sizing) {
    const auto &op = l.op;
    const auto &a = l.a;
    U pc = l.pc;
    if (op.empty())
      return {};
    if (op == ".arch") {
      nargs(l, 1);
      if (a[0] != (xlen == 64 ? "mica64" : "mica32"))
        throw Error("architecture mismatch");
      return {};
    }
    if (op == ".text" || op == ".data" || op == ".rodata" || op == ".bss") {
      nargs(l, 0);
      return {};
    }
    if (op == ".equ" || op == ".set") {
      nargs(l, 2);
      if (sizing) {
        if (op == ".equ" && sy.contains(a[0]))
          throw Error("duplicate constant " + a[0]);
        sy[a[0]] = num(a[1], false);
      }
      return {};
    }
    if (op == ".assert") {
      if (a.size() != 1 && a.size() != 2)
        throw Error(".assert expr[,message]");
      if (!sizing && num(a[0], false) == 0) {
        std::string detail = a.size() == 2 ? a[1] : a[0];
        throw Error("assembly assertion failed: " + detail);
      }
      return {};
    }
    if (op == ".error") {
      if (a.size() != 1) throw Error(".error expects one string");
      throw Error("source requested error: " + a[0]);
    }
    if (op == ".align") {
      nargs(l, 1);
      U n = num(a[0], sizing);
      if (!n || n > 4096 || (n & (n - 1)))
        throw Error(".align requires power of two <=4096");
      return Bytes(size_t((U(0) - pc) & (n - 1)), 0);
    }
    if (op == ".org") {
      nargs(l, 1);
      U dest = num(a[0], sizing);
      if (dest < pc || dest - pc > 16 * 1024 * 1024)
        throw Error(".org cannot move backward or skip >16MiB");
      return Bytes(size_t(dest - pc), 0);
    }
    if (op == ".space") {
      if (a.size() != 1 && a.size() != 2)
        throw Error(".space count[,fill]");
      U n = num(a[0], sizing);
      if (n > 16 * 1024 * 1024)
        throw Error(".space exceeds 16MiB");
      U f = a.size() == 2 ? num(a[1], sizing) : 0;
      return Bytes(size_t(n), std::uint8_t(f));
    }
    if (op == ".byte" || op == ".half" || op == ".word" || op == ".quad") {
      int n = op == ".byte" ? 1 : op == ".half" ? 2 : op == ".word" ? 4 : 8;
      if (a.empty())
        throw Error(op + " requires values");
      Bytes out;
      for (auto &v : a) {
        U t = num(v, sizing);
        if (!sizing && n < 8 && t > mask(8 * n) &&
            !(std::bit_cast<S>(t) >= -(S(1) << (8 * n - 1)) &&
              std::bit_cast<S>(t) <= (S(1) << (8 * n - 1)) - 1))
          throw Error("data value does not fit " + op);
        append(out, t, n);
      }
      return out;
    }
    if (op == ".ascii" || op == ".asciz") {
      if (a.empty())
        throw Error(op + " requires at least one quoted string");
      Bytes b;
      for (auto &item : a) {
        if (item.size() < 2 || item.front() != '"' || item.back() != '"')
          throw Error("expected quoted string");
        for (size_t k = 1; k + 1 < item.size(); k++) {
          char c = item[k];
          if (c == '\\') {
            if (++k + 1 > item.size())
              throw Error("bad escape");
            c = item[k];
            if (c == 'n')
              c = '\n';
            else if (c == 'r')
              c = '\r';
            else if (c == 't')
              c = '\t';
            else if (c == '0')
              c = '\0';
            else if (c != '\\' && c != '"')
              throw Error("unsupported escape");
          }
          b.push_back(std::uint8_t(c));
        }
        if (op == ".asciz")
          b.push_back(0);
      }
      return b;
    }
    if (pc % 2)
      throw Error("instruction at odd address; use .align 2");
    if (auto it = R.find(op); it != R.end()) {
      if (op == "mul" && !multiply)
        throw Error("mul needs --mul");
      if (op == "nop" || op == "wfi" || op == "fence" || op == "ecall" ||
          op == "eret" || op == "fence.i") {
        nargs(l, 0);
        return r16(it->second);
      }
      if (op == "jr" || op == "jalr" || op == "not" || op == "neg") {
        nargs(l, 1);
        return r16(it->second, reg(a[0], false));
      }
      nargs(l, 2);
      return r16(it->second, reg(a[0], false), reg(a[1], false));
    }
    if (op == "ret") {
      nargs(l, 0);
      return r16(13, 6);
    }
    if (op == "push" || op == "pop") {
      nargs(l, 1);
      int d = reg(a[0], false);
      if (d == 7)
        throw Error("cannot push/pop sp");
      Bytes b;
      if (op == "push") {
        join(b, i16(1, 7, U(0) - U(xlen / 8)));
        if (xlen == 32)
          join(b, m16(1, d, 7, 0));
        else
          join(b, e32(8, U(1 << 22) | U(d << 18) | U(7 << 14)));
      } else {
        if (xlen == 32)
          join(b, m16(0, d, 7, 0));
        else
          join(b, e32(8, U(d << 18) | U(7 << 14)));
        join(b, i16(1, 7, U(xlen / 8)));
      }
      return b;
    }
    if (op == "li" || op == "li32" || op == "li64") {
      nargs(l, 2);
      int d = reg(a[0], xreg);
      U n = num(a[1], sizing);
      Bytes b;
      if (op == "li64" && xlen != 64)
        throw Error("li64 requires --xlen 64");
      if (op == "li32" && xlen == 32 && !sizing)
        range(n, 32, std::bit_cast<S>(n) < 0, "li32");
      if (op == "li") {
        bool known = true;
        try {
          n = val(a[1], sy, false);
        } catch (const Error &) {
          known = false;
        }
        S sx = std::bit_cast<S>(n);
        if (known && d < 8 && sx >= -128 && sx <= 127)
          return i16(0, d, n);
        if (known && sx >= -32768 && sx <= 32767)
          return wide(2, d, n);
      }
      if (op == "li32" || (op == "li" && xlen == 32)) {
        if (!sizing && xlen == 32)
          range(n, 32, std::bit_cast<S>(n) < 0, "li literal");
        join(b, wide(0, d, (n >> 16) & 65535));
        join(b, wide(1, d, n & 65535));
        return b;
      }
      // Six 32-bit instructions, no scratch; value assembled high to low.
      join(b, wide(0, d, (n >> 48) & 65535));
      join(b, wide(1, d, (n >> 32) & 65535));
      join(b, e32(1, U(4 << 22) | U(d << 18) | U(d << 14) | 16));
      join(b, wide(1, d, (n >> 16) & 65535));
      join(b, e32(1, U(4 << 22) | U(d << 18) | U(d << 14) | 16));
      join(b, wide(1, d, n & 65535));
      return b; // six instructions; two shifts
    }
    if (auto it = I.find(op); it != I.end()) {
      if (op == "b") {
        nargs(l, 1);
        U off = sizing ? 0 : rel(num(a[0], false), pc, 2, 11);
        return i16(7, int((off >> 8) & 7), off);
      }
      nargs(l, 2);
      int d = reg(a[0], false);
      U n = 0;
      if (op == "bz" || op == "bnz")
        n = sizing ? 0 : rel(num(a[1], false), pc, 2, 8);
      else {
        n = num(a[1], sizing);
        if (!sizing)
          range(n, op == "shli" || op == "shri" ? 5 : 8,
                op == "li8" || op == "addi", op);
      }
      return i16(it->second, d, n);
    }
    if (auto it = MEM.find(op); it != MEM.end()) {
      nargs(l, 2);
      int d = reg(a[0], false);
      auto [base, off] = mem(a[1], sy, sizing, false);
      auto [kind, scale] = it->second;
      if (!sizing) {
        if (std::bit_cast<S>(off) % scale)
          throw Error("memory offset must be multiple of " +
                      std::to_string(scale));
        range(U(std::bit_cast<S>(off) / scale), 5, true, "memory offset");
      }
      return m16(kind, d, base, U(std::bit_cast<S>(off) / scale));
    }
    if (auto it = ALU.find(op); it != ALU.end()) {
      if (op == "mul3" && !multiply)
        throw Error("mul3 needs --mul");
      nargs(l, 3);
      return alu3(0, it->second, reg(a[0], xreg), reg(a[1], xreg),
                  reg(a[2], xreg));
    }
    if (auto it = BITOPS.find(op); it != BITOPS.end()) {
      if (!bitops)
        throw Error(op + " needs --bitops");
      const int opcode = it->second;
      const bool unary = (opcode <= 3 || opcode >= 17);
      nargs(l, unary ? 2 : 3);
      return alu3(11, opcode, reg(a[0], xreg), reg(a[1], xreg),
                  unary ? 0 : reg(a[2], xreg));
    }
    if (auto it = IMM.find(op); it != IMM.end()) {
      nargs(l, 3);
      int d = reg(a[0], xreg), ra = reg(a[1], xreg);
      U n = num(a[2], sizing);
      if (!sizing)
        range(n, (it->second >= 4 ? xlen == 64 ? 6 : 5 : 14), it->second == 0,
              op);
      return e32(1,
                 U(it->second << 22) | U(d << 18) | U(ra << 14) | (n & 0x3fff));
    }
    if (auto it = WIDE.find(op); it != WIDE.end()) {
      nargs(l, 2);
      U imm = num(a[1], sizing);
      if (!sizing)
        range(imm, 16, it->second == 2, op);
      return wide(it->second, reg(a[0], xreg), imm);
    }
    if (auto it = BR.find(op); it != BR.end()) {
      nargs(l, 3);
      int a0 = reg(a[0], xreg), b0 = reg(a[1], xreg);
      U n = sizing ? 0 : rel(num(a[2], false), pc, 4, 14);
      return e32(3, U(it->second << 22) | U(a0 << 18) | U(b0 << 14) | n);
    }
    if (op == "j" || op == "call") {
      nargs(l, 1);
      U n = sizing ? 0 : rel(num(a[0], false), pc, 4, 24);
      return e32(4, U((op == "call") << 24) | n);
    }
    if (op == "dbnz") {
      if (!flow)
        throw Error("dbnz needs --flow");
      nargs(l, 2);
      int d = reg(a[0], xreg);
      if (d == 0)
        throw Error("dbnz counter cannot be x0");
      U displacement = sizing ? 0 : rel(num(a[1], false), pc, 4, 20);
      return e32(9, U(d << 20) | displacement);
    }
    if (auto it = FLOW.find(op); it != FLOW.end()) {
      if (!flow)
        throw Error(op + " needs --flow");
      if (a.size() != 2 && a.size() != 3)
        throw Error(op + " data,[base][,stride]");
      int opcode = it->second;
      if ((opcode & 3) == 3 && xlen != 64)
        throw Error(op + " requires --xlen 64");
      int data = reg(a[0], xreg);
      auto [base, offset] = mem(a[1], sy, sizing, xreg);
      if (!sizing && offset)
        throw Error("flow memory operand must be [base] without offset");
      if (base == 0 || base == data)
        throw Error(
            "post-increment base must be writable and distinct from data register");
      U stride = a.size() == 3 ? num(a[2], sizing) : U(1 << (opcode & 3));
      if (a.size() == 2 && data < 8 && base < 8)
        return r16(23 + opcode, data, base);
      if (!sizing)
        range(stride, 14, true, "post-increment stride");
      return e32(10, U(opcode << 22) | U(data << 18) | U(base << 14) |
                         (stride & 16383));
    }
    if (auto it = SYS.find(op); it != SYS.end()) {
      if (it->second >= 2 && !atomic)
        throw Error(op + " needs --atomic");
      if (it->second >= 6 && xlen != 64)
        throw Error(op + " requires --xlen 64");
      int d = 0, ra = 0, rb = 0;
      U aux = 0;
      if (op == "csrr" || op == "csrw") {
        nargs(l, 2);
        auto csr = op == "csrr" ? a[1] : a[0];
        auto cit = CSRS.find(lower(csr));
        aux = cit == CSRS.end() ? num(csr, sizing) : U(cit->second);
        if (!sizing)
          range(aux, 8, false, "CSR number");
        if (op == "csrr")
          d = reg(a[0], xreg);
        else
          ra = reg(a[1], xreg);
      } else if (op == "lr.w" || op == "lr.q") {
        nargs(l, 2);
        d = reg(a[0], xreg);
        auto [base, off] = mem(a[1], sy, sizing, xreg);
        ra = base;
        if (!sizing && off)
          throw Error("atomic memory requires [base] only");
      } else {
        nargs(l, 3);
        d = reg(a[0], xreg);
        rb = reg(a[1], xreg);
        auto [base, off] = mem(a[2], sy, sizing, xreg);
        ra = base;
        if (!sizing && off)
          throw Error("atomic memory requires [base] only");
      }
      return e32(5, U(it->second << 20) | U(d << 16) | U(ra << 12) |
                        U(rb << 8) | aux);
    }
    if (auto it = W32.find(op); it != W32.end()) {
      if (xlen != 64)
        throw Error(op + " needs --xlen 64");
      if (op == "mulw3" && !multiply)
        throw Error("mulw3 needs --mul");
      nargs(l, 3);
      return alu3(7, it->second, reg(a[0], xreg), reg(a[1], xreg),
                  reg(a[2], xreg));
    }
    if (auto it = MX.find(op); it != MX.end()) {
      if (xlen != 64)
        throw Error(op + " needs --xlen 64");
      nargs(l, 2);
      int d = reg(a[0], xreg);
      auto [base, off] = mem(a[1], sy, sizing, xreg);
      if (!sizing) {
        range(off, 14, true, "64-bit memory byte offset");
        int align = op == "ldq" || op == "stq"     ? 8
                    : op == "ldws" || op == "ldwu" ? 4
                    : op == "ldhs"                 ? 2
                                                   : 1;
        if (std::bit_cast<S>(off) % align)
          throw Error("unaligned " + op + " offset");
      }
      return e32(8, U(it->second << 22) | U(d << 18) | U(base << 14) |
                        (off & 0x3fff));
    }
    if (op == "vclear") {
      if (!simd)
        throw Error("vclear needs --simd");
      nargs(l, 1);
      int d = reg(a[0], false, true);
      return e32(6, U(5 << 20) | U(d << 17) | U(d << 14) | U(d << 11));
    }
    if (op.starts_with("vmacc.")) {
      if (!simd)
        throw Error("vmacc requires --simd");
      nargs(l, 4);
      auto d = reg(a[0], false, true), s = reg(a[1], false, true),
           t = reg(a[2], false, true), tmp = reg(a[3], false, true);
      if (tmp == d || tmp == s || tmp == t)
        throw Error("vmacc scratch must differ from dst and sources");
      Line mul = l;
      mul.op = "vmul." + op.substr(6);
      mul.a = {a[3], a[1], a[2]};
      Line add = l;
      add.op = "vadd." + op.substr(6);
      add.a = {a[0], a[0], a[3]};
      add.pc = pc + 4;
      auto b = enc(mul, sizing);
      join(b, enc(add, sizing));
      return b;
    }
    if (op.starts_with("v")) {
      auto parts = split(std::regex_replace(op, std::regex(R"(\.)"), ","));
      if (parts.empty() || !V.contains(parts[0]))
        throw Error("unknown vector mnemonic " + op);
      if (!simd)
        throw Error(op + " needs --simd");
      int vop = V.at(parts[0]);
      int d = 0, ra = 0, rb = 0, lane = 0, mode = 0;
      if (vop == 16 || vop == 17) {
        if (parts.size() != 1)
          throw Error("vld/vst have no lane suffix");
        nargs(l, 2);
        d = reg(a[0], false, true);
        auto [base, off] = mem(a[1], sy, sizing, false);
        if (!sizing && off)
          throw Error("vld/vst no offset");
        ra = base;
      } else {
        if (parts.size() < 2 || parts[1].size() < 2 ||
            (parts[1][0] != 'u' && parts[1][0] != 's'))
          throw Error("vector operations require .u8/.s16 etc");
        auto width = parts[1].substr(1);
        if (width == "8")
          lane = 0;
        else if (width == "16")
          lane = 1;
        else if (width == "32")
          lane = 2;
        else if (width == "64")
          lane = 3;
        else
          throw Error("invalid lane width");
        mode = parts[1][0] == 's';
        bool sat = false, rnd = false;
        for (size_t k = 2; k < parts.size(); k++) {
          if (parts[k] == "sat" && !sat)
            sat = true;
          else if (parts[k] == "rnd" && !rnd)
            rnd = true;
          else
            throw Error("invalid or repeated vector modifier");
        }
        if (sat && vop > 2)
          throw Error(".sat only supports vector add/sub/mul");
        if (rnd && vop != 7 && vop != 8)
          throw Error(".rnd only supports vector right shifts");
        if (vop == 15 && (lane != 0 || sat || rnd))
          throw Error("vdot8 only supports 8-bit lanes");
        mode |= sat ? 2 : 0;
        mode |= rnd ? 4 : 0;
        if (vop == 13 || vop == 14) {
          nargs(l, 2);
          d = reg(a[0], false, true);
          ra = reg(a[1], false, true);
        } else {
          nargs(l, 3);
          d = reg(a[0], false, true);
          ra = reg(a[1], false, true);
          rb = reg(a[2], false, true);
        }
      }
      return e32(6, U(vop << 20) | U(d << 17) | U(ra << 14) | U(rb << 11) |
                        U(lane << 9) | U(mode << 6));
    }
    throw Error("unknown instruction/directive: " + op);
  }

public:
  Assembler(int w, bool xr, bool v, bool a, bool m, bool f, bool bits)
      : xlen(w), xreg(xr), simd(v), atomic(a), multiply(m), flow(f),
        bitops(bits) {}
  const Symbols& symbols() const { return sy; }
  std::pair<Bytes, std::vector<Line>> assemble(const fs::path &path) {
    lines.clear();
    sy.clear();
    macros.clear();
    unique = 0;
    expanded_lines = 0;
    include_stack.clear();
    const auto absolute = fs::weakly_canonical(path);
    include_stack.push_back(absolute);
    parse(expand(read(absolute, 0), 0));
    include_stack.clear();
    U pc = 0;
    for (auto &l : lines) {
      l.pc = pc;
      if (!l.label.empty()) {
        if (sy.contains(l.label))
          throw Error(l.src.filename + ":" + std::to_string(l.src.line) +
                      ": duplicate label " + l.label);
        sy[l.label] = pc;
      }
      try {
        auto b = enc(l, true);
        l.size = b.size();
        if (pc > 32 * 1024 * 1024 || b.size() > 32 * 1024 * 1024 - pc)
          throw Error("program image exceeds 32MiB");
        pc += b.size();
      } catch (const Error &e) {
        throw Error(l.src.filename + ":" + std::to_string(l.src.line) + ": " +
                    e.what() + "\n    " + l.src.text);
      }
    }
    Bytes out;
    for (auto &l : lines) {
      try {
        auto b = enc(l, false);
        if (b.size() != l.size)
          throw Error("unstable size: use explicit li32/li64 for symbol loads");
        join(out, b);
      } catch (const Error &e) {
        throw Error(l.src.filename + ":" + std::to_string(l.src.line) + ": " +
                    e.what() + "\n    " + l.src.text);
      }
    }
    return {out, lines};
  }
};
static void write_intel_hex(const fs::path &path, const Bytes &bytes) {
  std::ofstream out(path);
  if (!out)
    throw Error("cannot write hex");
  unsigned base = 0xffff;
  for (size_t offset = 0; offset < bytes.size(); offset += 16) {
    unsigned hi = unsigned(offset >> 16);
    auto record = [&](std::uint8_t type, U address, const Bytes &data) {
      unsigned sum = unsigned(data.size()) + unsigned((address >> 8) & 255) +
                     unsigned(address & 255) + type;
      out << ':' << std::hex << std::uppercase << std::setfill('0')
          << std::setw(2) << data.size() << std::setw(4) << (address & 0xffff)
          << std::setw(2) << int(type);
      for (auto c : data) {
        out << std::setw(2) << int(c);
        sum += c;
      }
      out << std::setw(2) << ((-sum) & 255) << '\n';
    };
    if (hi != base) {
      base = hi;
      record(4, 0, Bytes{std::uint8_t(hi >> 8), std::uint8_t(hi)});
    }
    size_t take = std::min<size_t>(16, bytes.size() - offset);
    if ((offset & 0xffff) + take > 65536)
      take = 65536 - (offset & 0xffff);
    record(0, offset,
           Bytes(bytes.begin() + std::ptrdiff_t(offset),
                 bytes.begin() + std::ptrdiff_t(offset + take)));
  }
  out << ":00000001FF\n";
}
int main(int argc, char **argv) {
  try {
    fs::path input, output, hex, listing, mapfile;
    int xlen = 32;
    bool xr = false, v = false, a = false, m = false, fl = false, bit = false;
    for (int i = 1; i < argc; i++) {
      std::string s = argv[i];
      auto next = [&]() {
        if (i + 1 >= argc)
          throw Error("missing argument after " + s);
        return std::string(argv[++i]);
      };
      if (s == "--xlen") {
        auto w = next();
        if (w != "32" && w != "64")
          throw Error("--xlen must be 32 or 64");
        xlen = std::stoi(w);
      } else if (s == "--trap") {
      } else if (s == "--bitops")
        bit = true;
      else if (s == "--flow")
        fl = true;
      else if (s == "--xreg")
        xr = true;
      else if (s == "--simd")
        v = true;
      else if (s == "--atomic")
        a = true;
      else if (s == "--mul")
        m = true;
      else if (s == "-o" || s == "--output")
        output = next();
      else if (s == "--hex")
        hex = next();
      else if (s == "--listing")
        listing = next();
      else if (s == "--map")
        mapfile = next();
      else if (s == "--help") {
        std::cout
            << "mica-as [--xlen 32|64] [--xreg] [--mul] [--simd] [--atomic] [--flow] [--bitops] [--trap] [-o path] [--hex path] [--listing path] [--map path] file.mica\n";
        return 0;
      } else if (s.starts_with('-'))
        throw Error("unknown flag: " + s);
      else if (!input.empty())
        throw Error("only one input file allowed");
      else
        input = s;
    }
    if (input.empty())
      throw Error("missing source (use --help)");
    if (output.empty()) {
      output = input;
      output.replace_extension(".bin");
    }
    Assembler assembler(xlen, xr, v, a, m, fl, bit);
    auto [bytes, lines] = assembler.assemble(input);
    std::ofstream f(output, std::ios::binary);
    if (!f)
      throw Error("cannot write " + output.string());
    f.write(reinterpret_cast<const char *>(bytes.data()),
            std::streamsize(bytes.size()));
    if (!f)
      throw Error("write failed");
    if (!hex.empty())
      write_intel_hex(hex, bytes);
    if (!mapfile.empty()) {
      std::ofstream map(mapfile);
      if (!map) throw Error("cannot write symbol map");
      std::map<U, std::vector<std::string>> by_address;
      for (const auto& [name, address] : assembler.symbols())
        by_address[address].push_back(name);
      for (auto& [address, names] : by_address) {
        std::sort(names.begin(), names.end());
        for (const auto& name : names)
          map << "0x" << std::hex << std::setw(8) << std::setfill('0') << address
              << " " << name << "\n";
      }
      if (!map) throw Error("symbol map write failed");
    }
    if (!listing.empty()) {
      std::ofstream l(listing);
      if (!l)
        throw Error("cannot write listing");
      for (auto &s : lines) {
        l << std::hex << std::setfill('0') << std::setw(8) << s.pc << "  ";
        for (size_t i = 0; i < s.size && i < 12; i++)
          l << std::setw(2) << int(bytes.at(size_t(s.pc) + i)) << ' ';
        l << "  " << s.src.filename << ":" << std::dec << s.src.line << "  "
          << s.src.text << '\n';
      }
    }
    std::cout << "mica-as: wrote " << bytes.size() << " bytes (MICA-" << xlen
              << ") to " << output.string() << "\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "mica-as: " << e.what() << "\n";
    return 1;
  }
}
