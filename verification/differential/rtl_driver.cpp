// Deterministic variable-latency memory model for the MICA retirement port.
// SPDX-License-Identifier: MIT
#include "Vmica_core_txn.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <random>
#include <sstream>
#include <stdexcept>
#include <vector>
#ifndef MICA_XLEN
#define MICA_XLEN 32
#endif
using U = std::uint64_t;
struct Request {
  bool active = false, offered = false, error = false, write = false;
  U address = 0, data = 0, strobes = 0;
  unsigned delay = 0, size = 0;
};
int main(int argc, char **argv) {
  try {
    if (argc < 3)
      throw std::runtime_error(
          "driver firmware.bin trace.jsonl [seed] [reset-cycle]");
    VerilatedContext context;
    Vmica_core_txn cpu{&context};
    std::ifstream code(argv[1], std::ios::binary);
    if (!code)
      throw std::runtime_error("cannot read firmware");
    std::vector<unsigned char> ram((std::istreambuf_iterator<char>(code)), {});
    if (ram.size() > 65536)
      throw std::runtime_error("firmware too large");
    ram.resize(65536);
    std::ofstream trace(argv[2]);
    if (!trace)
      throw std::runtime_error("cannot write trace");
    std::mt19937 rng(argc > 3 ? unsigned(std::stoul(argv[3])) : 1);
    const unsigned reset_cycle = argc > 4 ? unsigned(std::stoul(argv[4])) : 0;
    unsigned fetches = 0, loads = 0, stores = 0, events = 0;
    U led = 0;
    const unsigned irq_memory = argc > 5 ? unsigned(std::stoul(argv[5])) : 0;
    const unsigned irq_retired = argc > 6 ? unsigned(std::stoul(argv[6])) : 0;
    const unsigned irq_delay = argc > 7 ? unsigned(std::stoul(argv[7])) : 0;
    unsigned retired = 0, wake_cycle = 0;
    bool irq_line = false, irq_fired = false;
    Request insn, data;
    bool i_stalled = false, d_stalled = false;
    U stalled_i = 0, stalled_d = 0, stalled_wdata = 0, stalled_strb = 0;
    unsigned stalled_size = 0;
    bool stalled_write = false;
    for (unsigned cycle = 0; cycle < 2000000; cycle++) {
      if (wake_cycle && cycle == wake_cycle) {
        irq_line = true;
        irq_fired = true;
      }
      const bool reset = cycle < 3 || (reset_cycle && cycle == reset_cycle);
      if (reset) {
        insn = {};
        data = {};
        i_stalled = d_stalled = false;
        if (cycle == reset_cycle) {
          trace.close();
          trace.open(argv[2]);
          events = 0;
        }
      }
      cpu.clk_i = 0;
      cpu.rst_ni = !reset;
      cpu.irq_i = irq_line;
      cpu.i_req_ready = !reset && !insn.active && (rng() % 4 != 0);
      cpu.d_req_ready = !reset && !data.active && (rng() % 4 != 0);
      if (insn.active && !insn.offered) {
        if (insn.delay)
          --insn.delay;
        else
          insn.offered = true;
      }
      if (data.active && !data.offered) {
        if (data.delay)
          --data.delay;
        else
          data.offered = true;
      }
      cpu.i_rsp_valid = insn.offered;
      cpu.i_rsp_rdata = std::uint32_t(insn.data);
      cpu.i_rsp_error = insn.error;
      cpu.d_rsp_valid = data.offered;
      cpu.d_rsp_rdata = data.data;
      cpu.d_rsp_error = data.error;
      cpu.eval();
      if (wake_cycle && cycle < wake_cycle &&
          (cpu.i_req_valid || cpu.d_req_valid))
        throw std::runtime_error("memory request issued while WFI is asleep");
      if (i_stalled && (!cpu.i_req_valid || cpu.i_req_addr != stalled_i))
        throw std::runtime_error(
            "instruction request changed under backpressure");
      if (d_stalled &&
          (!cpu.d_req_valid || cpu.d_req_addr != stalled_d ||
           cpu.d_req_wdata != stalled_wdata ||
           cpu.d_req_wstrb != stalled_strb ||
           cpu.d_req_write != stalled_write || cpu.d_req_size != stalled_size))
        throw std::runtime_error("data request changed under backpressure");
      i_stalled = cpu.i_req_valid && !cpu.i_req_ready;
      stalled_i = cpu.i_req_addr;
      d_stalled = cpu.d_req_valid && !cpu.d_req_ready;
      stalled_d = cpu.d_req_addr;
      stalled_wdata = cpu.d_req_wdata;
      stalled_strb = cpu.d_req_wstrb;
      stalled_write = cpu.d_req_write;
      stalled_size = cpu.d_req_size;
      const bool ia = cpu.i_req_valid && cpu.i_req_ready,
                 da = cpu.d_req_valid && cpu.d_req_ready;
      const bool ir = cpu.i_rsp_valid && cpu.i_rsp_ready,
                 dr = cpu.d_rsp_valid && cpu.d_rsp_ready;
      if (ia) {
        insn = {};
        insn.active = true;
        insn.delay = rng() % 9;
        insn.address = cpu.i_req_addr;
        insn.error = insn.address > ram.size() - 4;
        if (!insn.error)
          for (unsigned j = 0; j < 4; j++)
            insn.data |= U(ram.at(size_t(insn.address) + j)) << (8 * j);
        ++fetches;
      }
      if (da) {
        data = {};
        data.active = true;
        data.delay = rng() % 11;
        data.address = cpu.d_req_addr;
        data.write = cpu.d_req_write;
        data.size = 1u << cpu.d_req_size;
        const U base = data.address & ~U(MICA_XLEN / 8 - 1);
        if (data.address <= ram.size() &&
            data.size <= ram.size() - data.address) {
          if (data.write) {
            for (unsigned j = 0; j < MICA_XLEN / 8; j++)
              if (cpu.d_req_wstrb & (1u << j))
                ram.at(size_t(base) + j) =
                    static_cast<unsigned char>(cpu.d_req_wdata >> (8 * j));
          } else
            for (unsigned j = 0; j < MICA_XLEN / 8; j++)
              data.data |= U(ram.at(size_t(base) + j)) << (8 * j);
        } else if (data.size <= 4 && data.write &&
                   data.address == 0xffff0010ULL) {
          led = cpu.d_req_wdata & 255;
        } else if (data.size <= 4 && !data.write &&
                   data.address == 0xffff0010ULL) {
          data.data = led << (8 * (data.address - base));
        } else if (data.size <= 4 && !data.write &&
                   data.address == 0xffff000cULL) {
          data.data = 0;
        } else if (data.size <= 4 && data.write &&
                   data.address == 0xffff0000ULL) {
          std::cout.put(char(cpu.d_req_wdata & 255));
        } else
          data.error = true;
        if (data.write)
          ++stores;
        else
          ++loads;
        if (!irq_fired && irq_memory && loads + stores == irq_memory) {
          irq_line = true;
          irq_fired = true;
        }
      }
      cpu.clk_i = 1;
      cpu.eval();
      context.timeInc(1);
      if (ir)
        insn = {};
      if (dr)
        data = {};
      if (cpu.trace_valid) {
        if (wake_cycle && cycle < wake_cycle)
          throw std::runtime_error(
              "instruction retired before the WFI wake event");
        if (cpu.trace_trap && (U(cpu.trace_cause) >> (MICA_XLEN - 1)))
          irq_line = false;
        trace << "{\"order\":" << cpu.trace_order
              << ",\"pc\":" << U(cpu.trace_pc) << ",\"insn\":" << cpu.trace_insn
              << ",\"length\":" << unsigned(cpu.trace_length)
              << ",\"retired\":" << (cpu.trace_retired ? "true" : "false")
              << ",\"next_pc\":" << U(cpu.trace_next_pc)
              << ",\"trap\":" << (cpu.trace_trap ? "true" : "false")
              << ",\"cause\":" << U(cpu.trace_cause) << ",\"regs\":[";
        for (unsigned r = 0; r < 16; r++) {
          U value = cpu.trace_regs[r * (MICA_XLEN / 32)];
#if MICA_XLEN == 64
          value |= U(cpu.trace_regs[r * 2 + 1]) << 32;
#endif
          trace << (r ? "," : "") << value;
        }
        trace << "],\"memory\":[";
        if (cpu.trace_mem_valid)
          trace << "{\"addr\":" << U(cpu.trace_mem_addr)
                << ",\"data\":" << U(cpu.trace_mem_data)
                << ",\"bytes\":" << unsigned(cpu.trace_mem_bytes)
                << ",\"write\":" << (cpu.trace_mem_write ? "true" : "false")
                << "}";
        trace << "]}\n";
        ++events;
        if (cpu.trace_retired)
          ++retired;
        if (!irq_fired && !wake_cycle && irq_retired && retired == irq_retired)
          wake_cycle = cycle + 1 + irq_delay;
      }
      if (cpu.halt_o) {
        trace.close();
        cpu.final();
        std::cerr << "{\"cycles\":" << cycle - 2 << ",\"fetches\":" << fetches
                  << ",\"loads\":" << loads << ",\"stores\":" << stores
                  << ",\"events\":" << events
                  << ",\"fault\":" << unsigned(cpu.fault_o) << "}\n";
        return cpu.fault_o ? 2 : 0;
      }
    }
    throw std::runtime_error("RTL cycle limit exceeded");
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
