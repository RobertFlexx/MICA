# MICA 3.0 development contract

Revision 1 starts the MICA 3.0 development line from commit d29511c. It retains
the ISA 2.0 development encodings and the explicit 1.0 compatibility mode.
The SDK version, architecture roadmap and diagram collection advance to 3.0;
there is no new ELF ISA flag, mandatory instruction or incompatible machine code.
Existing command defaults remain compatible. Select MICA-2C/2E/2L or --mica2
for the 2.0 contract. The release metadata records this distinction.

## Architectural rules

MICA is a load/store architecture. Arithmetic operates on explicit registers,
integer overflow wraps, and ordinary instructions introduce no condition-code
register or hidden loop state. Halfword-aligned 16/32-bit encodings remain.
Optional hardware must disappear from the compact configuration when disabled.
The minimum processor keeps eight register slots and no multiplier, divider,
vector file, cache hierarchy or speculative pipeline.

Post-increment memory and counted branches are the retained compound operations.
A streaming load combines one transaction with one related pointer update.
Both destination and base commit after a successful response; a base/destination
alias is illegal. A store's fault-atomic behavior also depends on the fabric.
Counted branches update an ordinary register, preserve normal interrupt context,
and wrap at XLEN. Stack accesses remain one transaction per instruction.

No instruction is removed in this revision. Short destructive arithmetic and
long three-register arithmetic share semantics but offer different register reach
and operand preservation. W32 forms retain their defined sign extension.
Signed/unsigned loads remain distinct because their architectural results differ.
The generated [inventory](INSTRUCTION_INVENTORY.md) accounts for every mnemonic,
allocation mask, field, behavior, extension, latency assumption and RTL status.
The [conformance matrix](../verification/INSTRUCTION_MATRIX.md) records actual
software and hardware integration separately.

## Complexity decisions

| Decision | Opcode space | State / control cost | Benefit and acceptance |
| --- | --- | --- | --- |
| Select existing short arithmetic and literals in the compiler | None | None in hardware; bounded assembler selection | Smaller complete C image; native/emulator/RTL checks required |
| Accept conventional three-operand scalar syntax | None | Existing R or ALU3 encoding; no new decoder case | Concise source; explicit add3 and peers retain their fixed long encoding |
| Share optional multiplication across short/ALU3/W32 | None | One combinational low product, common read muxes, operand enables; no new FSM state | Fewer mapped DSPs and LUTs; routed timing and physical power remain unmeasured |
| Retain optional F and counted branches | Existing only | Existing second commit slot and transactional LSU | Measured stream kernels; no general compiler advantage established |
| Retain eight and sixteen register profiles | None | Existing parameterized storage/read muxes | Expanded compiler path reduces spills; compact core remains selectable |
| Defer multi-register push/pop hardware | None allocated | Would need per-register progress and restart/fault rules | Existing assembly expansion remains; no measured whole-program justification |
| Defer MAC, packed saturation and high-half multiply | None allocated | Would add arithmetic/result-selection logic and verification | Require numerical oracle, compiler selection, mapped area and timing first |
| Defer new compact register mappings | None allocated | Would change decoder/ABI compatibility | Actual compiler frequencies and spill results must justify a versioned encoding |
| Defer hidden hardware loop state and replay buffer | None allocated | Would add state, invalidation and interrupt interactions | Existing tagged parcel reuse and ordinary counted branches remain |
| Defer pipeline, security and vector hardware claims | None allocated | No implementation exists | Separate experimental work and acceptance gates; no advertised processor support |

The multiplier's first shared implementation reduced DSP count but increased
LUTs by adding independent register-selection logic. That implementation was
rejected. Sharing the scalar read muxes produced the retained design. Resource
counts and code-size results are in the [development report](../engineering/MICA3_DEVELOPMENT.md).
Marginal per-instruction silicon area and routed critical paths are unmeasured.

## Compatibility and acceptance

ISA 2.0 object flags and relocation identifiers do not change. Fixed 1.0 images,
mixed-revision rejection, signed F faults, word arithmetic and reserved encodings
remain regression requirements. A future incompatible instruction redesign needs
a distinct object contract, explicit tooling selection and migration tests.

MICA 3.0 is a development baseline, not a completed third ISA specification.
An optimizing compiler, independent ROM/RAM sections, a pipeline, hardware
atomics/SIMD, protection, bounded external response times, physical FPGA
validation and energy measurements remain open. No production, safety,
radiation or security qualification is implied.
