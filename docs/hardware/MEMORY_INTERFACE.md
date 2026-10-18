# Transactional memory ports

`mica_core_txn` has separate instruction and data request/response ports in clk_i.
At most one request is outstanding on each port; the current FSM does not overlap
instruction and data phases. Acceptance occurs on a rising edge with req_valid AND
req_ready. The sender holds all request fields stable while valid and not ready.
Each accepted request owns exactly one response. A slave may delay arbitrarily, but
must eventually respond for program progress.

Instruction requests carry an XLEN address aligned to 4 and return 32 data bits plus
error. The CPU selects a halfword and fetches again if a long instruction crosses a
word. No second response can be consumed before the first is owned. Data requests
carry the **effective byte address**, write flag, size (log2 byte count), XLEN write
data and XLEN/8 byte strobes. Write data/strobes are shifted into the addressed lane
of the containing aligned XLEN bus beat. A successful read returns that whole beat;
the CPU shifts/extracts/sign-extends its access. Byte/half/word/doubleword accesses
must be naturally aligned and fit one beat.

Response valid/data/error remain stable until rsp_ready. The CPU asserts ready only
in its wait states. A successful store response acknowledges the write; an error
store response guarantees **no memory write occurred**. Reads with error provide no
usable data. Errors trap at the original instruction PC, and F base/destination
writes are discarded. Invalid/alignment faults emit no data request. There are no
transaction IDs, retries or cancellations except reset.

Reset cancels unaccepted requests and all outstanding response ownership in **both**
CPU and fabric. Old responses must not reappear after release. An accepted write
already applied before reset need not be undone. SRAM contents are not cleared by
reset. External bridges must implement this reset contract; resetting the CPU alone
while a bridge retains stale responses is unsupported. The legacy `mica_core`
adapter cannot report external bus faults and assumes immediate memory at its legacy
pins. New designs use the transactional ports.

`rtl/verilog/mica_sram_txn.v` implements two synchronous memory ports and one held
response per port. Its DATA_W is 32 or 64; RAM_BYTES is a power of two and a
multiple of DATA_W/8. A word read occurs on acceptance; data is registered. Read
data has no reset, preserving block RAM inference. The same-port write response
returns old data. Cross-port same-word read/write collisions are unspecified; the
single-core SoC never issues such overlapping accesses.

Initialization uses **word** files, padded through the configured RAM size:
`bin2mem8.py in.bin out.mem32 --width 32 --pad-bytes 4096` (64 for MICA64). The
script's old 8-bit default is retained for archived byte fixtures. No-file SRAM
contents are unspecified until written. Do not feed byte or Intel HEX files to the
word SRAM. One 64 KiB/32-bit standalone mapping inferred 16 RAMB36E1 blocks with
Yosys; this is a synthesis result, not timing closure.
