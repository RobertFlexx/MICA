# MICA documentation

MICA's documents separate architectural behavior, implementation details and
measured results. The ISA manual defines what a program observes; the hardware and
toolchain guides explain how the current implementations provide it.

## Getting started

| Task | Guide |
| --- | --- |
| Build the SDK and run tests | [Building MICA](../BUILDING.md) |
| Check supported features and unfinished work | [SDK status](../SDK_STATUS.md) |
| Write and assemble a program | [Assembler](toolchain/ASSEMBLER.md), [dialect](toolchain/DIALECT.md) |
| Link multiple source files | [Linker](toolchain/LINKER.md), [object format](toolchain/OBJECT_FORMAT.md) |
| Run or debug firmware | [Emulator](toolchain/EMULATOR.md), [debugger](toolchain/DEBUGGING.md) |
| Use assembly library routines | [Runtime](RUNTIME.md) |
| Build the Arty A7 target | [FPGA guide](hardware/FPGA_BUILD.md), [board connections](hardware/BOARD_CONNECTIONS.md) |

## Architecture

The [ISA manual](architecture/ISA.md) covers instruction formats, arithmetic,
addressing and execution. [Encoding tables](architecture/ENCODINGS.md) are generated
from the machine-readable ISA definition. Separate references cover
[registers](architecture/REGISTERS.md), the [assembly ABI](architecture/ABI.md),
[CSRs](architecture/CSR.md), [execution mode](architecture/PRIVILEGE.md),
[exceptions](architecture/EXCEPTIONS.md), [interrupts](architecture/INTERRUPTS.md),
[memory ordering](architecture/MEMORY_MODEL.md) and the emulator's [vector
extension](architecture/SIMD.md).

## Hardware

The [microarchitecture guide](hardware/MICROARCHITECTURE.md) follows an instruction
through the reference core. [Memory ports](hardware/MEMORY_INTERFACE.md),
[peripherals](hardware/PERIPHERALS.md) and [clock/reset
behavior](hardware/CLOCK_RESET.md) define the integration contracts.
[Drawings](hardware/DATAPATH.md) include RTL signal widths and actual SoC module
connections.

[Synthesis](hardware/SYNTHESIS.md) describes resource mapping;
[timing](hardware/TIMING.md) records the current timing-validation status. The
[pipeline page](hardware/PIPELINE.md) describes the next microarchitecture work and
its dependency on the retirement reference.

## Verification and measurements

Start with [testing](verification/TESTING.md), then the [retirement
comparison](verification/DIFFERENTIAL.md), [formal checks](verification/FORMAL.md)
and [coverage limits](verification/COVERAGE.md).
[Benchmarks](research/BENCHMARKS.md), [activity measurements](research/POWER.md) and
[design experiments](research/DESIGN_EXPERIMENTS.md) explain the research methods.
[Prior art](research/PRIOR_ART.md) identifies related designs and comparison
requirements.

The [repository audit](engineering/AUDIT.md) records the original defects. The [r2
report](engineering/IMPLEMENTATION_REPORT.md) brings together the fixes, results and
remaining work, with [archived evidence](engineering/results/README.md). Older
top-level document paths remain as navigation links for existing readers.
