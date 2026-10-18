// Bounded, endian-explicit MICA ELF64 reader/writer and relocation engine.
// Experimental private machine number 0xff4d, not an assigned ELF e_machine.
// SPDX-License-Identifier: MIT
#pragma once
#include <algorithm>
#include <bit>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <sstream>
#include <set>
#include <vector>
namespace mica::elf {
using U = std::uint64_t;
using S = std::int64_t;
using Bytes = std::vector<std::uint8_t>;
constexpr U max_file = 64 * 1024 * 1024;
constexpr unsigned machine = 0xff4d;
enum RelocType : unsigned {
  ABS32 = 1,
  ABS64 = 2,
  LI32 = 3,
  LI64 = 4,
  PCREL8 = 5,
  PCREL11 = 6,
  PCREL14 = 7,
  PCREL20 = 8,
  PCREL24 = 9
};
struct Symbol {
  std::string name;
  U value = 0;
  unsigned bind = 0, section = 1;
};
struct Reloc {
  U offset = 0;
  unsigned type = 0;
  std::string symbol;
  S addend = 0;
};
struct Object {
  unsigned type = 1, width = 32, features = 0;
  U entry = 0, base = 0;
  Bytes image;
  std::vector<Symbol> symbols;
  std::vector<Reloc> relocs;
};
[[noreturn]] inline void fail(const std::string &s) {
  throw std::runtime_error(s);
}
inline void bounds(const Bytes &b, U at, U n) {
  if (at > b.size() || n > b.size() - at)
    fail("ELF offset/size outside file");
}
inline U get(const Bytes &b, U at, unsigned n) {
  bounds(b, at, n);
  U value = 0;
  for (unsigned j = 0; j < n; j++)
    value |= U(b[size_t(at) + j]) << (8 * j);
  return value;
}
inline void put(Bytes &b, U at, U value, unsigned n) {
  bounds(b, at, n);
  for (unsigned j = 0; j < n; j++)
    b[size_t(at) + j] = std::uint8_t(value >> (8 * j));
}
inline void append(Bytes &b, U value, unsigned n) {
  if (n > max_file || b.size() > max_file - n)
    fail("ELF exceeds 64MiB");
  U at = b.size();
  b.resize(b.size() + n);
  put(b, at, value, n);
}
inline Bytes read_file(const std::filesystem::path &p) {
  const auto n = std::filesystem::file_size(p);
  if (n > max_file)
    fail("input exceeds 64MiB");
  std::ifstream f(p, std::ios::binary);
  if (!f)
    fail("cannot read " + p.string());
  Bytes b(static_cast<size_t>(n));
  f.read(reinterpret_cast<char *>(b.data()), static_cast<std::streamsize>(n));
  if (!f)
    fail("input read failed");
  return b;
}
inline void write_file(const std::filesystem::path &p, const Bytes &b) {
  std::ofstream f(p, std::ios::binary);
  if (!f)
    fail("cannot write " + p.string());
  f.write(reinterpret_cast<const char *>(b.data()),
          static_cast<std::streamsize>(b.size()));
  if (!f)
    fail("output write failed");
}
inline bool is_elf(const Bytes &b) {
  return b.size() >= 4 && b[0] == 127 && b[1] == 'E' && b[2] == 'L' &&
         b[3] == 'F';
}
inline std::string string_at(const Bytes &b, U table, U size, U offset) {
  bounds(b, table, size);
  if (offset >= size)
    fail("ELF string offset outside table");
  std::string s;
  for (U i = offset; i < size; i++) {
    char c = char(b[size_t(table + i)]);
    if (!c)
      return s;
    if (s.size() >= 4096)
      fail("ELF string exceeds 4096 bytes");
    s += c;
  }
  fail("unterminated ELF string");
}
inline Object parse(const Bytes &b) {
  bounds(b, 0, 64);
  if (!is_elf(b) || b[4] != 2 || b[5] != 1 || b[6] != 1 ||
      get(b, 18, 2) != machine || get(b, 20, 4) != 1)
    fail("expected little-endian experimental MICA ELF64");
  Object o;
  o.type = unsigned(get(b, 16, 2));
  if (o.type != 1 && o.type != 2)
    fail("unsupported ELF file type");
  if (get(b, 52, 2) != 64 || get(b, 58, 2) != 64 || get(b, 56, 2) != 0)
    fail("unsupported ELF header layout");
  U flags = get(b, 48, 4);
  if (flags & ~U(0xff01))
    fail("unknown MICA ELF flags");
  o.width = (flags & 1) ? 64 : 32;
  o.features = unsigned(flags >> 8);
  o.entry = get(b, 24, 8);
  U shoff = get(b, 40, 8), n = get(b, 60, 2), names = get(b, 62, 2);
  if (n < 6 || n > 32 || names >= n)
    fail("invalid ELF section count/index");
  bounds(b, shoff, n * 64);
  auto sh = [&](U i, U field, unsigned bytes = 8) {
    return get(b, shoff + i * 64 + field, bytes);
  };
  if (sh(names, 4, 4) != 3)
    fail("section names are not a string table");
  U nameoff = sh(names, 24), namesize = sh(names, 32);
  std::map<std::string, U> sections;
  for (U i = 1; i < n; i++) {
    U at = sh(i, 24), size = sh(i, 32), align = sh(i, 48);
    if (sh(i, 4, 4) == 8)
      fail("NOBITS sections unsupported in MICA image objects");
    bounds(b, at, size);
    if (align > 4096 || (align && (align & (align - 1))))
      fail("invalid ELF section alignment");
    auto name = string_at(b, nameoff, namesize, sh(i, 0, 4));
    if (!sections.emplace(name, i).second)
      fail("duplicate ELF section name");
  }
  for (auto name :
       {".mica.image", ".rela.mica.image", ".symtab", ".strtab", ".shstrtab"})
    if (!sections.contains(name))
      fail(std::string("missing ELF section ") + name);
  U image = sections.at(".mica.image"), sym = sections.at(".symtab"),
    str = sections.at(".strtab"), rel = sections.at(".rela.mica.image");
  if (n != 6 || sh(image, 4, 4) != 1 || sh(image, 8) != 7 ||
      sh(sym, 4, 4) != 2 || sh(str, 4, 4) != 3 || sh(rel, 4, 4) != 4 ||
      sh(sym, 40, 4) != str || sh(rel, 40, 4) != sym ||
      sh(rel, 44, 4) != image || sh(sym, 56) != 24 || sh(rel, 56) != 24 ||
      sh(sym, 32) % 24 || sh(rel, 32) % 24)
    fail("unsupported MICA ELF section/entry layout");
  o.base = sh(image, 16);
  if (o.type == 1 && o.base)
    fail("relocatable image has nonzero address");
  U imageoff = sh(image, 24), imagesize = sh(image, 32);
  if (imagesize > 32 * 1024 * 1024)
    fail("image exceeds 32MiB");
  o.image.assign(b.begin() + std::ptrdiff_t(imageoff),
                 b.begin() + std::ptrdiff_t(imageoff + imagesize));
  if (o.base > ~U(0) - imagesize ||
      (o.width == 32 && o.base + imagesize > 0x100000000ULL))
    fail("ELF image address range overflow");
  if (o.type == 2 &&
      ((o.entry & 1) || o.entry < o.base || o.entry - o.base >= imagesize))
    fail("ELF entry outside image or unaligned");
  if (o.type == 1 && o.entry)
    fail("relocatable object has a nonzero entry");
  U ns = sh(sym, 32) / 24;
  if (!ns || ns > 200000 || sh(sym, 44, 4) > ns)
    fail("invalid ELF symbol count");
  std::vector<std::string> symbol_names(ns);
  std::set<std::string> unique_names;
  U symbol_text = 0, relocation_text = 0;
  for (U i = 0; i < ns; i++) {
    U pos = sh(sym, 24) + i * 24;
    unsigned info = unsigned(get(b, pos + 4, 1));
    Symbol s{string_at(b, sh(str, 24), sh(str, 32), get(b, pos, 4)),
             get(b, pos + 8, 8), info >> 4, unsigned(get(b, pos + 6, 2))};
    if (i == 0) {
      if (!s.name.empty() || s.value || s.bind || s.section)
        fail("bad null ELF symbol");
      continue;
    }
    if (s.name.empty() || s.bind > 2 || (info & 15) != 0 ||
        (s.section != 0 && s.section != image && s.section != 0xfff1))
      fail("unsupported ELF symbol");
    if (s.section == image) {
      if (o.type == 1 && s.value > o.image.size())
        fail("symbol outside image");
      s.section = 1;
    }
    auto valid_char = [](unsigned char c) {
      return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
             (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '$';
    };
    if (!std::all_of(s.name.begin(), s.name.end(), valid_char) ||
        (s.name[0] >= '0' && s.name[0] <= '9'))
      fail("unsupported ELF symbol name");
    symbol_text += s.name.size();
    if (symbol_text > 16 * 1024 * 1024 || !unique_names.insert(s.name).second)
      fail("duplicate or excessive ELF symbol names");
    symbol_names[size_t(i)] = s.name;
    o.symbols.push_back(s);
  }
  U nr = sh(rel, 32) / 24;
  if (nr > 200000)
    fail("too many ELF relocations");
  if (o.type == 2 && nr)
    fail("executable retains relocations");
  for (U i = 0; i < nr; i++) {
    U at = sh(rel, 24) + i * 24, info = get(b, at + 8, 8), index = info >> 32;
    if (!index || index >= ns)
      fail("invalid relocation symbol index");
    unsigned type = unsigned(info & 0xffffffff);
    if (type < ABS32 || type > PCREL24)
      fail("unsupported MICA relocation type");
    relocation_text += symbol_names[size_t(index)].size();
    if (relocation_text > 16 * 1024 * 1024)
      fail("excessive ELF relocation names");
    o.relocs.push_back({get(b, at, 8), type, symbol_names[size_t(index)],
                        std::bit_cast<S>(get(b, at + 16, 8))});
  }
  return o;
}
inline Bytes encode(Object o) {
  std::stable_sort(
      o.symbols.begin(), o.symbols.end(), [](const auto &a, const auto &b) {
        return (a.bind == 0) != (b.bind == 0) ? a.bind == 0 : a.name < b.name;
      });
  Bytes strings{0}, syms(24, 0), rels, shnames{0};
  std::map<std::string, U> indices;
  auto add_string = [](Bytes &table, const std::string &s) {
    if (s.size() > 4096 || table.size() + s.size() + 1 > 16 * 1024 * 1024)
      fail("ELF string table limit exceeded");
    U at = table.size();
    table.insert(table.end(), s.begin(), s.end());
    table.push_back(0);
    return at;
  };
  unsigned locals = 1;
  for (const auto &s : o.symbols) {
    if (!indices.emplace(s.name, indices.size() + 1).second)
      fail("duplicate symbol in object");
    append(syms, add_string(strings, s.name), 4);
    append(syms, U(s.bind << 4), 1);
    append(syms, 0, 1);
    append(syms, s.section, 2);
    append(syms, s.value, 8);
    append(syms, 0, 8);
    if (!s.bind)
      ++locals;
  }
  for (const auto &r : o.relocs) {
    auto it = indices.find(r.symbol);
    if (it == indices.end())
      fail("relocation references missing symbol");
    append(rels, r.offset, 8);
    append(rels, (it->second << 32) | r.type, 8);
    append(rels, std::bit_cast<U>(r.addend), 8);
  }
  const std::vector<std::string> names{
      "", ".mica.image", ".rela.mica.image", ".symtab", ".strtab", ".shstrtab"};
  std::vector<U> nameids{0};
  for (size_t i = 1; i < names.size(); i++)
    nameids.push_back(add_string(shnames, names[i]));
  Bytes out(64, 0);
  out[0] = 127;
  out[1] = 'E';
  out[2] = 'L';
  out[3] = 'F';
  out[4] = 2;
  out[5] = 1;
  out[6] = 1;
  put(out, 16, o.type, 2);
  put(out, 18, machine, 2);
  put(out, 20, 1, 4);
  put(out, 24, o.entry, 8);
  put(out, 48, (o.width == 64 ? 1u : 0u) | (o.features << 8), 4);
  put(out, 52, 64, 2);
  put(out, 58, 64, 2);
  put(out, 60, 6, 2);
  put(out, 62, 5, 2);
  std::vector<Bytes> content{{}, o.image, rels, syms, strings, shnames};
  std::vector<U> offsets(6);
  for (size_t i = 1; i < content.size(); i++) {
    while (out.size() % 8)
      out.push_back(0);
    offsets[i] = out.size();
    if (content[i].size() > max_file - out.size())
      fail("ELF exceeds 64MiB");
    out.insert(out.end(), content[i].begin(), content[i].end());
  }
  while (out.size() % 8)
    out.push_back(0);
  U shoff = out.size();
  put(out, 40, shoff, 8);
  out.resize(out.size() + 6 * 64, 0);
  for (size_t i = 1; i < content.size(); i++) {
    U at = shoff + i * 64;
    put(out, at, nameids[i], 4);
    put(out, at + 4, i == 1 ? 1 : i == 2 ? 4 : i == 3 ? 2 : 3, 4);
    put(out, at + 8, i == 1 ? 7 : 0, 8);
    put(out, at + 16, i == 1 ? o.base : 0, 8);
    put(out, at + 24, offsets[i], 8);
    put(out, at + 32, content[i].size(), 8);
    put(out, at + 40, i == 2 ? 3 : i == 3 ? 4 : 0, 4);
    put(out, at + 44, i == 2 ? 1 : i == 3 ? locals : 0, 4);
    put(out, at + 48, i == 1 ? 16 : i == 2 || i == 3 ? 8 : 1, 8);
    put(out, at + 56, i == 2 || i == 3 ? 24 : 0, 8);
  }
  if (out.size() > max_file)
    fail("ELF exceeds 64MiB");
  return out;
}
inline U add_signed(U a, S b) {
  if (b >= 0) {
    if (U(b) > ~U(0) - a)
      fail("relocation addition overflow");
    return a + U(b);
  }
  U magnitude = U(0) - std::bit_cast<U>(b);
  if (magnitude > a)
    fail("negative relocation value");
  return a - magnitude;
}
inline void relocate(Bytes &image, const Reloc &r, U target, U location) {
  target = add_signed(target, r.addend);
  if (r.type >= LI32 && (r.offset & 1))
    fail("unaligned instruction relocation");
  U size = r.type == LI64                         ? 24
           : r.type == LI32 || r.type == ABS64    ? 8
           : r.type == ABS32 || r.type >= PCREL14 ? 4
                                                  : 2;
  bounds(image, r.offset, size);
  if (r.type == ABS32 || r.type == ABS64) {
    if (r.type == ABS32 && target > 0xffffffffULL)
      fail("ABS32 relocation overflow");
    put(image, r.offset, target, unsigned(size));
    return;
  }
  auto payload = [&](U offset) {
    U h = get(image, offset, 2);
    if ((h >> 14) != 3)
      fail("relocation expects long instruction");
    return ((h & 1023) << 16) | get(image, offset + 2, 2);
  };
  auto set_payload = [&](U offset, U p) {
    put(image, offset, (get(image, offset, 2) & 0xfc00) | ((p >> 16) & 1023),
        2);
    put(image, offset + 2, p & 65535, 2);
  };
  if (r.type == LI32 || r.type == LI64) {
    if (r.type == LI32 && target > 0xffffffffULL)
      fail("LI32 relocation overflow");
    const unsigned chunks = r.type == LI32 ? 2 : 4;
    const U positions[4] = {0, 4, 12, 20};
    unsigned reg = unsigned((payload(r.offset) >> 16) & 15);
    for (unsigned i = 0; i < chunks; i++) {
      U off = r.offset + positions[i], p = payload(off), h = get(image, off, 2);
      if (((h >> 10) & 15) != 2 || (p >> 20) != (i == 0 ? 0u : 1u) ||
          ((p >> 16) & 15) != reg)
        fail("LI relocation instruction template mismatch");
      set_payload(off, (p & ~U(65535)) |
                           ((target >> (16 * (chunks - 1 - i))) & 65535));
    }
    if (chunks == 4)
      for (U off : {r.offset + 8, r.offset + 16}) {
        U p = payload(off);
        if (((get(image, off, 2) >> 10) & 15) != 1 ||
            p != ((U(4) << 22) | (U(reg) << 18) | (U(reg) << 14) | 16))
          fail("LI64 shift template mismatch");
      }
    return;
  }
  const unsigned bits = r.type == PCREL8    ? 8
                        : r.type == PCREL11 ? 11
                        : r.type == PCREL14 ? 14
                        : r.type == PCREL20 ? 20
                                            : 24;
  S delta = std::bit_cast<S>(target - (location + size));
  if ((delta & 1) || delta / 2 < -(S(1) << (bits - 1)) ||
      delta / 2 > ((S(1) << (bits - 1)) - 1))
    fail("PC-relative relocation out of range/alignment");
  const U value = std::bit_cast<U>(delta / 2) & ((U(1) << bits) - 1),
          h = get(image, r.offset, 2);
  if (bits <= 11) {
    unsigned op = unsigned((h >> 11) & 7);
    if ((h >> 14) != 1 || (bits == 8 ? (op != 5 && op != 6) : op != 7))
      fail("short branch relocation mismatch");
    put(image, r.offset, (h & ~((U(1) << bits) - 1)) | value, 2);
  } else {
    unsigned major = unsigned((h >> 10) & 15);
    if ((bits == 14 && major != 3) || (bits == 20 && major != 9) ||
        (bits == 24 && major != 4))
      fail("long branch relocation mismatch");
    U p = payload(r.offset);
    set_payload(r.offset, (p & ~((U(1) << bits) - 1)) | value);
  }
}
inline const char *relocation_name(unsigned type) {
  constexpr const char *names[] = {"NONE",    "ABS32",  "ABS64",   "LI32",
                                   "LI64",    "PCREL8", "PCREL11", "PCREL14",
                                   "PCREL20", "PCREL24"};
  return type <= PCREL24 ? names[type] : "INVALID";
}
} // namespace mica::elf
