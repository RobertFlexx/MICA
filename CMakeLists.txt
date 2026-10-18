cmake_minimum_required(VERSION 3.20)
project(
  MICA_SDK
  VERSION 2.0
  LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_executable(mica-as toolchain/assembler.cpp)
target_compile_options(mica-as PRIVATE -Wall -Wextra -Wpedantic -Wconversion)
add_executable(mica-run sim/emulator.cpp)
target_compile_options(mica-run PRIVATE -Wall -Wextra -Wpedantic -Wconversion)
add_executable(mica-dis toolchain/disasm.cpp)
target_compile_options(mica-dis PRIVATE -Wall -Wextra -Wpedantic -Wconversion)
add_executable(mica-ld toolchain/linker.cpp)
foreach(tool IN ITEMS mica-objdump mica-nm mica-objcopy)
  add_executable(${tool} toolchain/object_tools.cpp)
  target_compile_definitions(${tool} PRIVATE MICA_TOOL="${tool}")
endforeach()
foreach(tool IN ITEMS mica-ld mica-objdump mica-nm mica-objcopy)
  target_compile_options(${tool} PRIVATE -Wall -Wextra -Wpedantic -Wconversion)
endforeach()
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
include(GNUInstallDirs)
install(
  TARGETS mica-as
          mica-run
          mica-dis
          mica-ld
          mica-objdump
          mica-nm
          mica-objcopy
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY stdlib/ DESTINATION ${CMAKE_INSTALL_DATADIR}/mica/stdlib)
install(DIRECTORY isa/ DESTINATION ${CMAKE_INSTALL_DATADIR}/mica/isa)
enable_testing()
add_test(NAME generated_isa
         COMMAND ${Python3_EXECUTABLE}
                 ${CMAKE_SOURCE_DIR}/scripts/generate_isa.py --check)
add_test(
  NAME integration
  COMMAND
    ${CMAKE_COMMAND} -E env MICA_AS=$<TARGET_FILE:mica-as>
    MICA_RUN=$<TARGET_FILE:mica-run> MICA_DIS=$<TARGET_FILE:mica-dis>
    ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/integration.py)

add_test(
  NAME binary_compatibility
  COMMAND
    ${CMAKE_COMMAND} -E env MICA_AS=$<TARGET_FILE:mica-as>
    MICA_RUN=$<TARGET_FILE:mica-run> ${Python3_EXECUTABLE}
    ${CMAKE_SOURCE_DIR}/tests/binary_compatibility.py --as
    $<TARGET_FILE:mica-as>)

add_test(
  NAME fast_differential
  COMMAND
    ${CMAKE_COMMAND} -E env MICA_AS=$<TARGET_FILE:mica-as>
    MICA_RUN=$<TARGET_FILE:mica-run> ${Python3_EXECUTABLE}
    ${CMAKE_SOURCE_DIR}/tests/fast_paths.py)

add_test(NAME engineering
         COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/engineering.py
                 --tools $<TARGET_FILE_DIR:mica-as>)
add_test(NAME mica2
         COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/mica2.py
                 --tools $<TARGET_FILE_DIR:mica-as>)
add_test(
  NAME elf_revision
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/elf_revision.py
          --tools $<TARGET_FILE_DIR:mica-as>)
add_test(
  NAME isa_contract
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/isa_contract.py
          --tools $<TARGET_FILE_DIR:mica-as>)
add_test(NAME format_safety COMMAND ${Python3_EXECUTABLE}
                                    ${CMAKE_SOURCE_DIR}/tests/format_safety.py)
add_test(
  NAME mica2_density
  COMMAND
    ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/benchmarks/mica2_code_size.py
    --assembler $<TARGET_FILE:mica-as> --emulator $<TARGET_FILE:mica-run>)

add_test(
  NAME firmware_examples
  COMMAND
    ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/scripts/build_firmware.py --tools
    $<TARGET_FILE_DIR:mica-as> --output ${CMAKE_CURRENT_BINARY_DIR}/firmware)

option(MICA_FUZZ "Build Clang libFuzzer targets" OFF)
if(MICA_FUZZ)
  if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "MICA_FUZZ needs Clang libFuzzer")
  endif()
  add_executable(mica-elf-fuzz verification/fuzz/elf_fuzzer.cpp)
  target_compile_options(
    mica-elf-fuzz PRIVATE -fsanitize=fuzzer,address,undefined
                          -fno-omit-frame-pointer)
  target_link_options(mica-elf-fuzz PRIVATE -fsanitize=fuzzer,address,undefined)
  add_test(
    NAME fuzz_seed
    COMMAND
      ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/scripts/seed_fuzz.py
      --assembler $<TARGET_FILE:mica-as> --output
      ${CMAKE_CURRENT_BINARY_DIR}/fuzz-corpus)
  add_test(NAME fuzz_elf
           COMMAND mica-elf-fuzz -seed=42 -runs=10000 -max_len=4096 -timeout=2
                   -rss_limit_mb=512 ${CMAKE_CURRENT_BINARY_DIR}/fuzz-corpus)
  set_tests_properties(fuzz_elf PROPERTIES DEPENDS fuzz_seed)
endif()

install(DIRECTORY runtime/ DESTINATION ${CMAKE_INSTALL_DATADIR}/mica/runtime)
install(
  DIRECTORY examples/
  DESTINATION ${CMAKE_INSTALL_DATADIR}/mica/examples
  FILES_MATCHING
  PATTERN "*.mica")
install(
  DIRECTORY firmware/
  DESTINATION ${CMAKE_INSTALL_DATADIR}/mica/firmware
  FILES_MATCHING
  PATTERN "*.mica")
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(DIRECTORY docs/ DESTINATION ${CMAKE_INSTALL_DOCDIR})
install(FILES README.md BUILDING.md SDK_STATUS.md LICENSE CHANGELOG.md
        DESTINATION ${CMAKE_INSTALL_DOCDIR})
set(CPACK_PACKAGE_NAME "mica-sdk")
set(CPACK_PACKAGE_VERSION "2.0")
set(CPACK_PACKAGE_FILE_NAME
    "mica-sdk-2.0-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}")
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_SOURCE_DIR}/LICENSE")
include(CPack)
add_test(
  NAME documentation
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/scripts/check_docs.py
          --assembler $<TARGET_FILE:mica-as>)
