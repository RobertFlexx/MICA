# V software reference

V is optional and implemented only by the emulator. It is absent from all verified
hardware profiles. Eight writable 128-bit registers v0..v7 hold little-endian packed
lanes: lane 0 occupies the low bits. Lane codes 0..3 mean 8/16/32/64-bit elements;
unsigned .uN and signed .sN select comparisons and saturation. All vector opcode
allocations and per-operation pseudocode appear in ENCODINGS.md. Binary arithmetic
reads both sources before overwriting VD. Unary abs/neg require VB=0; low six
payload bits are always zero.

Add/sub/mul wrap at lane width unless .sat is selected; .sat clamps the full
mathematical result to the lane's signed/unsigned range. Unsigned subtraction clamps
below zero. Products use a double-width intermediate. Logical operations and
comparisons do not accept .sat. Shifts use the corresponding B lane modulo lane
width. SHR is logical and SAR is arithmetic regardless of suffix. .rnd is legal only
on right shifts and rounds division by 2^count to nearest, ties to even, including
negative inputs. Count 0 leaves the value unchanged. Abs/neg wrap on the most
negative value. Comparisons produce all-ones or zero lanes.

VDOT8 accepts only byte lanes and forms four groups of four products, summing each
group into a wrapping 32-bit output lane. ZIP low/high interleaves the selected
halves. UNZIP low/high concatenates the even/odd elements of A then B. There is no
widening/narrowing or lane insertion instruction in r2. VMACC is a two-instruction
pseudo using an explicit distinct scratch vector, not fused.

VLD/VST transfer sixteen naturally aligned **RAM** bytes; vector mode/lane/VB and
reserved fields must be zero. Validate the full range before any lane or memory
update, so a boundary fault cannot partially modify a vector or RAM. Scalar operands
for vector memory use the short base register field.

Vector CSR enabled starts at 1 when V exists; enabled=0 makes V execution illegal.
Any V execution marks dirty=1. These two CSRs do not implement protected lazy state
sharing. All 1024 bits must be preserved if a task switch permits V in multiple
tasks. The example scheduler does not use V. Numerical tests cover
saturation, packing, shifts, dot products and memory in the interpreter; no SIMD
hardware synthesis or parallel/narrow-lane energy comparison exists.
