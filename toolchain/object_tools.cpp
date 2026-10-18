// Real ELF inspection and firmware conversion utilities, sharing one reader.
// SPDX-License-Identifier: MIT
#include "common/elf.hpp"
#include <iomanip>
#include <iostream>
#ifndef MICA_TOOL
#define MICA_TOOL "mica-objdump"
#endif
namespace e = mica::elf;
int main(int argc, char **argv) {
  const std::string tool = MICA_TOOL;
  try {
    std::vector<std::string> files;
    std::string format = "binary";
    for (int i = 1; i < argc; i++) {
      std::string opt = argv[i];
      if (opt == "--version") {
        std::cout << tool << " 2.0 development\n";
        return 0;
      }
      if (opt == "--help") {
        std::cout
            << (tool == "mica-objcopy"
                    ? "mica-objcopy [-O binary|ihex|mem8] firmware.elf output\n"
                    : tool + " file.o|firmware.elf\n");
        return 0;
      }
      if (opt == "-O" && tool == "mica-objcopy") {
        if (++i == argc)
          e::fail("-O needs a format");
        format = argv[i];
      } else if (opt.starts_with('-'))
        e::fail("unknown option: " + opt);
      else
        files.push_back(opt);
    }
    if (files.size() != (tool == "mica-objcopy" ? 2u : 1u))
      e::fail("incorrect number of input/output files (use --help)");
    auto o = e::parse(e::read_file(files[0]));
    if (tool == "mica-nm") {
      std::sort(o.symbols.begin(), o.symbols.end(),
                [](auto &a, auto &b) { return a.name < b.name; });
      for (const auto &s : o.symbols) {
        char type = s.section == 0        ? 'U'
                    : s.section == 0xfff1 ? 'A'
                    : s.bind == 2         ? 'W'
                    : s.bind == 1         ? 'T'
                                          : 't';
        std::cout << std::hex << std::setfill('0') << std::setw(16) << s.value
                  << " " << type << " " << s.name << "\n";
      }
    } else if (tool == "mica-objdump") {
      std::cout << "experimental MICA ELF64 type=" << o.type
                << " XLEN=" << o.width << " entry=0x" << std::hex << o.entry
                << "\n"
                << "section .mica.image address=0x" << o.base << " size=0x"
                << o.image.size() << " flags=WAX\n"
                << "symbols " << std::dec << o.symbols.size() << "\n";
      for (const auto &s : o.symbols)
        std::cout << s.name << " value=0x" << std::hex << s.value
                  << " binding=" << s.bind << " section=" << s.section << "\n";
      std::cout << "relocations " << std::dec << o.relocs.size() << "\n";
      for (const auto &r : o.relocs)
        std::cout << "0x" << std::hex << r.offset << " "
                  << e::relocation_name(r.type) << " " << r.symbol << " "
                  << std::dec << r.addend << "\n";
    } else {
      if (format != "binary" && format != "ihex" && format != "mem8")
        e::fail("unsupported output format: " + format);
      if (o.type != 2)
        e::fail(
            "objcopy requires a linked executable; link relocatable objects first");
      if (format == "binary")
        e::write_file(files[1], o.image);
      else {
        std::ofstream out(files[1]);
        if (!out)
          e::fail("cannot write converted firmware");
        if (format == "mem8")
          for (auto b : o.image)
            out << std::hex << std::setfill('0') << std::setw(2) << unsigned(b)
                << '\n';
        else if (format == "ihex") {
          if (o.base > 0xffffffffULL ||
              o.image.size() > 0x100000000ULL - o.base)
            e::fail("Intel HEX address exceeds 32 bits");
          auto record = [&](unsigned kind, unsigned addr,
                            const e::Bytes &bytes) {
            unsigned sum =
                unsigned(bytes.size()) + (addr >> 8) + (addr & 255) + kind;
            out << ':' << std::hex << std::uppercase << std::setfill('0')
                << std::setw(2) << bytes.size() << std::setw(4) << addr
                << std::setw(2) << kind;
            for (auto b : bytes) {
              out << std::setw(2) << unsigned(b);
              sum += b;
            }
            out << std::setw(2) << ((-sum) & 255) << '\n';
          };
          e::U previous = ~e::U(0);
          for (size_t i = 0; i < o.image.size();) {
            e::U address = o.base + i, high = address >> 16;
            if (high != previous) {
              record(4, 0, {std::uint8_t(high >> 8), std::uint8_t(high)});
              previous = high;
            }
            size_t n = std::min<size_t>(
                {16, o.image.size() - i, size_t(65536 - (address & 65535))});
            record(0, unsigned(address & 65535),
                   e::Bytes(o.image.begin() + std::ptrdiff_t(i),
                            o.image.begin() + std::ptrdiff_t(i + n)));
            i += n;
          }
          record(1, 0, {});
        } else
          e::fail("unsupported output format: " + format);
        if (!out)
          e::fail("firmware conversion failed");
      }
    }
    return 0;
  } catch (const std::exception &x) {
    std::cerr << tool << ": " << x.what() << '\n';
    return 1;
  }
}
