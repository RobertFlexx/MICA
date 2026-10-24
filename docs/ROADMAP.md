# MICA development roadmap

MICA targets a compiler-supported, single-core microcontroller platform with
compact code, predictable memory and interrupts, and reproducible builds.
MICA-2C is the minimum configuration; MICA-2E adds registers and embedded
extensions, and MICA-2L provides an optional 64-bit target. Compatibility mode
preserves the frozen 1.0 firmware contract.

## Milestones

| Order | Milestone | Current state | Completion gate |
| --- | --- | --- | --- |
| 1 | Reliable assembly SDK | Local checks pass; remote CI pending | GCC/Clang builds, CTest, sanitizers/fuzzing, frozen fixtures, installed binary and extracted source checks |
| 2 | Compiler-ready object and ABI contract | In progress: revision flags, PC-relative addresses, compact branch relocations and object alignment implemented | Independent text/rodata/data/BSS sections, NOBITS, section alignment/relocations, ROM-to-RAM startup, specified C calling convention and reproducible negative tests |
| 3 | Minimum C toolchain | Experimental Clang IR subset works for MICA-2C/2E; compiled sensor firmware simulated | Maintained optimizing backend, unsupported C constructs, XLEN64, complete ABI and freestanding runtime |
| 4 | Smaller reference implementation | Synthesis baseline available | Matched bare-core and SoC synthesis, separate RAM/peripheral/counter costs, retirement equivalence and area/CPI results |
| 5 | FPGA platform validation | Board simulation complete; physical tests pending | Vivado implementation, routed timing, Arty A7 reset/boot and UART/RAM/timer/interrupt tests, archived constraints and logs |
| 6 | First pipelined core | Open | An implementation tested against the multicycle retirement reference, including hazards, stalls, branches, precise faults, interrupt boundaries and reset cancellation |
| 7 | Matched workload evaluation | Encoding comparisons available | Compiler-generated workloads with matched memory, options and clocks; code size, cycles, resources, timing and energy measurements |
| 8 | Optional system extensions | Emulator experiments/proposals | DSP/atomic RTL, task protection or multicore each require a separate specification, implementation, ordering/numerical tests and measured cost before profile promotion |

Milestones 2 and 3 form the compiler track; milestones 4 and 5 form the reference
hardware track. The pipeline uses milestone 4 as its baseline and repeats the
board validation in milestone 5. Workload evaluation requires a working compiler
and validated hardware. Optional extensions must remain independent of the
minimum profile's state and datapaths.

The [revision report](engineering/WORKFLOW_ISA_REVISION.md) records completed
toolchain and workflow work, including compact branch relocations, object
alignment, trap diagnostics and package validation.

## Next implementation sequence

1. Design independent ELF sections while retaining an explicit reader for existing
   image objects. Define section-local symbols, relocation ownership, alignment,
   BSS size limits and deterministic layout before changing the assembler/linker.
2. Specify the C ABI on top of the [assembly ABI](architecture/ABI.md): integer
   widths, arguments/returns, aggregates, varargs, stack frames and callee saves.
   Select a compiler backend and test leaf calls, recursion, spills and interrupts
   before growing the runtime.
3. Improve compiler register allocation and control-flow lowering before adding
   more instructions. Signed F loads are optional development additions; their
   DSP results do not establish general compiler benefits.
4. Reduce reference-core resources with measured experiments, then validate the
   board and a pipeline against the existing retirement interface. Every new
   implementation must retain precise faults and compatibility regressions.
5. Evaluate complete workloads with matched configurations. Report instruction
   count, emulator throughput, FPGA resources, timing and energy separately.

Physical validation requires Vivado and an Arty A7 board. The
[status table](../SDK_STATUS.md) tracks support; the
[research priorities](research/MICA2_PRIORITIES.md) describe planned experiments.

The [embedded report](engineering/EMBEDDED_REFINEMENT.md) tracks current C,
sensor, wakeup and optional integrity work. MICA-2D/2R/2S remain proposed.
Security isolation, ECC, a pipeline and qualification need separate implementation
and verification gates.
