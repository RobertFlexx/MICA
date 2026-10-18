// Build with Clang -fsanitize=fuzzer,address,undefined. No host file access.
#include "../../toolchain/common/elf.hpp"
#include "../../isa/encoding.hpp"
extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t *input,
                                      std::size_t size) {
  if (size > 65536)
    return 0;
  mica::elf::Bytes bytes(input, input + size);
  try {
    auto object = mica::elf::parse(bytes);
    auto encoded = mica::elf::encode(object);
    (void)mica::elf::parse(encoded);
    for (const auto &r : object.relocs) {
      auto image = object.image;
      try {
        mica::elf::relocate(image, r, 0, 0);
      } catch (const std::exception &) {
      }
    }
  } catch (const std::exception &) {
  }
  for (std::size_t i = 0; i + 4 <= size; i += 4)
    (void)mica::legal_encoding(
        std::uint16_t(bytes[i] | unsigned(bytes[i + 1]) << 8),
        std::uint32_t((unsigned(bytes[i]) & 3) << 24 |
                      unsigned(bytes[i + 1]) << 16 | unsigned(bytes[i + 2]) |
                      unsigned(bytes[i + 3]) << 8),
        64);
  return 0;
}
