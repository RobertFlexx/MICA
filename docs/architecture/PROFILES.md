# Processor profile contract

`isa/profiles/profiles.json` is the machine-readable profile list. Profile names
select XLEN, register budget and ISA options. Platform peripherals and register
integrity are separate RTL parameters. They do not silently change instruction
encodings or create a privilege level.

| Profile | State | Contract |
| --- | --- | --- |
| MICA-2C | Experimental scalar implementation | XLEN32, eight registers, 2C; compact MCU baseline without mandatory M/F/B/T, vector state or caches |
| MICA-2E | Experimental scalar implementation | XLEN32, sixteen registers, X/M/F/B/T/2C; enhanced embedded target, with no implemented memory protection |
| MICA-2L | Experimental scalar implementation | XLEN64, sixteen registers, X/M/F/B/T/2C; optional wider scalar target |
| MICA-2D | Proposed | 2E foundation; packed fixed-point DSP semantics, arithmetic hardware and numerical/deadline verification still required |
| MICA-2R | Proposed | 2E foundation; memory integrity, recovery policy, diagnostics and broader fault coverage still required |
| MICA-2S | Proposed | 2E foundation; privilege/isolation, immutable trust assumptions, verified boot, key/debug policy and security verification still required |

The proposed profiles are not runnable selections. Existing register parity and
watchdog blocks are useful research components but do not complete MICA-2R.
No DSP/security encoding is reserved merely by listing a profile.

2C instructions retain their encodings in 2E and 2L, but XLEN changes memory widths,
address wrapping and ABI layout. A 32-bit executable is not a 64-bit executable.
On the same XLEN, an executable's feature mask must be a subset of enabled
features. Short register operands always select x0..x7. New signed F loads require
2.0 development r2 hardware or newer. Earlier 2.0 implementations reject those
subopcodes; version 1.0 compatibility decoding remains separately selected.

The legacy MICA-C/E/64 profiles retain their 1.0 contract. MICA-DSP is an
emulator-only vector experiment; MICA-MP is a multicore proposal. Neither is a
verified hardware alternative to the scalar profiles above.

Smart infrastructure evaluation currently uses the compiled sensor demonstration.
Industrial/remote work uses watchdog and fault probes. DSP work uses signed
streaming and FIR kernels. Security, flight qualification, automotive safety
certification and physical low-power validation remain outside current support.
