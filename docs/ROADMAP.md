# Development priorities

The 2.0 reference core, toolchain and retirement tests provide a baseline for further
work. The immediate hardware priorities are the measured area cost, a first
pipelined implementation and Arty board bring-up. Toolchain work centers on
independent ELF sections, stronger diagnostics and compiler code generation.

The [implementation report](engineering/IMPLEMENTATION_REPORT.md#remaining-work)
explains these priorities and their validation needs. The [status
table](../SDK_STATUS.md) tracks the current support boundary. Multicore and SIMD
hardware need their own ordering and numerical tests before joining the verified
configurations.
