// MICA ELF image linker. SPDX-License-Identifier: MIT
#include "common/elf.hpp"
#include <iostream>
#include <regex>
#include <set>
namespace e = mica::elf;
int main(int argc, char **argv) {
  try {
    std::vector<std::filesystem::path> paths;
    std::filesystem::path output = "a.bin", elfout, mapout, script;
    std::string entry;
    e::U origin = 0, length = 32 * 1024 * 1024;
    for (int i = 1; i < argc; i++) {
      std::string opt = argv[i];
      auto next = [&]() {
        if (++i == argc)
          e::fail("missing argument for " + opt);
        return std::string(argv[i]);
      };
      if (opt == "-o")
        output = next();
      else if (opt == "--elf")
        elfout = next();
      else if (opt == "--map")
        mapout = next();
      else if (opt == "--base")
        origin = std::stoull(next(), nullptr, 0);
      else if (opt == "--entry")
        entry = next();
      else if (opt == "-T")
        script = next();
      else if (opt == "--version") {
        std::cout << "mica-ld 1.0 engineering-r2\n";
        return 0;
      } else if (opt == "--help") {
        std::cout
            << "mica-ld [-o firmware.bin] [--elf firmware.elf] [--map file] [-T image.ld] [--base N] [--entry SYMBOL] file.o ...\n";
        return 0;
      } else if (opt.starts_with('-'))
        e::fail("unknown option: " + opt);
      else
        paths.emplace_back(opt);
    }
    if (paths.empty())
      e::fail("no input objects");
    if (paths.size() > 1024)
      e::fail("more than 1024 input objects");
    if (!script.empty()) {
      auto bytes = e::read_file(script);
      std::string text(bytes.begin(), bytes.end());
      std::regex assignment(
          R"(^\s*(ORIGIN|LENGTH|ENTRY)\s*=\s*([A-Za-z0-9_.$]+)\s*;\s*$)");
      std::istringstream in(text);
      std::string line;
      std::set<std::string> seen;
      while (std::getline(in, line)) {
        auto comment = line.find('#');
        if (comment != std::string::npos)
          line.resize(comment);
        if (line.find_first_not_of(" \t\r") == line.npos)
          continue;
        std::smatch match;
        if (!std::regex_match(line, match, assignment))
          e::fail("invalid MICA image script statement: " + line);
        std::string name = match[1], value = match[2];
        if (!seen.insert(name).second)
          e::fail("duplicate script assignment");
        if (name == "ENTRY")
          entry = value;
        else {
          size_t consumed = 0;
          e::U n = std::stoull(value, &consumed, 0);
          if (consumed != value.size())
            e::fail("invalid script number");
          if (name == "ORIGIN")
            origin = n;
          else
            length = n;
        }
      }
    }
    if (origin & 15)
      e::fail("image origin must be 16-byte aligned");
    if (length > 32 * 1024 * 1024 || origin > ~e::U(0) - length)
      e::fail("invalid image memory region");
    std::vector<e::Object> inputs;
    std::vector<e::U> offsets;
    e::Object linked;
    linked.type = 2;
    linked.base = origin;
    e::U input_bytes = 0;
    for (const auto &path : paths) {
      input_bytes += std::filesystem::file_size(path);
      if (input_bytes > e::max_file)
        e::fail("combined input objects exceed 64MiB");
      auto o = e::parse(e::read_file(path));
      if (o.type != 1)
        e::fail("linker expects relocatable objects");
      if (!inputs.empty() && o.width != inputs.front().width)
        e::fail("cannot mix MICA32 and MICA64 objects");
      linked.width = o.width;
      linked.features |= o.features;
      while (linked.image.size() % 16)
        linked.image.push_back(0);
      offsets.push_back(linked.image.size());
      if (linked.image.size() > length ||
          o.image.size() > length - linked.image.size())
        e::fail("image exceeds memory region");
      linked.image.insert(linked.image.end(), o.image.begin(), o.image.end());
      inputs.push_back(std::move(o));
    }
    if (linked.width == 32 && origin + linked.image.size() > 0x100000000ULL)
      e::fail("image exceeds 32-bit address space");
    std::map<std::string, e::Symbol> globals;
    std::vector<std::map<std::string, e::Symbol>> locals(inputs.size());
    for (size_t i = 0; i < inputs.size(); i++)
      for (auto s : inputs[i].symbols) {
        if (!locals[i].emplace(s.name, s).second)
          e::fail("duplicate object symbol: " + s.name);
        if (!s.section)
          continue;
        if (s.section == 1)
          s.value += origin + offsets[i];
        if (!s.bind) {
          s.name = "$" + std::to_string(i) + "." + s.name;
          linked.symbols.push_back(s);
          continue;
        }
        auto it = globals.find(s.name);
        if (it == globals.end())
          globals.emplace(s.name, s);
        else if (it->second.bind == 1 && s.bind == 1)
          e::fail("multiple strong definitions: " + s.name);
        else if (it->second.bind == 2 && s.bind == 1)
          it->second = s;
      }
    for (size_t i = 0; i < inputs.size(); i++)
      for (const auto &r : inputs[i].relocs) {
        auto it = locals[i].find(r.symbol);
        if (it == locals[i].end())
          e::fail("missing relocation symbol");
        e::U target = 0;
        if (!it->second.bind && it->second.section)
          target = it->second.value +
                   (it->second.section == 1 ? origin + offsets[i] : 0);
        else if (auto g = globals.find(r.symbol); g != globals.end())
          target = g->second.value;
        else if (it->second.bind != 2)
          e::fail("undefined symbol: " + r.symbol);
        auto relocated = r;
        relocated.offset += offsets[i];
        e::relocate(linked.image, relocated, target, origin + relocated.offset);
      }
    for (const auto &[name, s] : globals) {
      (void)name;
      linked.symbols.push_back(s);
    }
    if (entry.empty() && globals.contains("_start"))
      entry = "_start";
    linked.entry = origin;
    if (!entry.empty()) {
      auto it = globals.find(entry);
      if (it == globals.end())
        e::fail("entry symbol undefined: " + entry);
      linked.entry = it->second.value;
    }
    if ((linked.entry & 1) || linked.entry < origin ||
        linked.entry >= origin + linked.image.size())
      e::fail("entry outside image or unaligned");
    // All validation precedes output creation, so failed links preserve outputs.
    auto elfbytes = e::encode(linked);
    e::write_file(output, linked.image);
    if (!elfout.empty())
      e::write_file(elfout, elfbytes);
    if (!mapout.empty()) {
      std::ofstream map(mapout);
      if (!map)
        e::fail("cannot write map");
      for (const auto &s : linked.symbols)
        map << "0x" << std::hex << s.value << " " << s.name << "\n";
      if (!map)
        e::fail("map write failed");
    }
    std::cout << "mica-ld: " << linked.image.size() << " bytes, entry 0x"
              << std::hex << linked.entry << "\n";
    return 0;
  } catch (const std::exception &x) {
    std::cerr << "mica-ld: " << x.what() << '\n';
    return 1;
  }
}
