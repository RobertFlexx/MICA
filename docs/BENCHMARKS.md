# Measurement notebook

## A code-density result we can reproduce today

Byte-copy inner loop in the basic ISA:

```asm
loop:
    ldbu x4,[x2]
    stb x4,[x1]
    addi x1,1
    addi x2,1
    addi x3,-1
    bnz x3,loop
```

Six 16-bit instructions = 12 bytes in the loop body.

The same loop with optional F:

```asm
loop:
    ldpi.b x4,[x2]
    stpi.b x4,[x1]
    dbnz x3,loop
```

Two 16-bit instructions and one 32-bit instruction = 8 bytes. That's a 33.3% body-size reduction and 50% fewer instructions per copied byte. Those percentages exclude setup, guard, function prologue/epilogue and memory data traffic. In the demonstration state machine, the nominal cycles for the two bodies are 12 versus 7, assuming combinational instruction/data memory with no waits. That is an estimate derived from the FSM, **not a measured IPC or timing result**.

An independent script can assemble both sequences and compare the emitted byte lengths. Look at `benchmarks/flow_density.py`. This is only one favorable case. It should not be used to state that MICA code is 33% smaller in general.

## Real metrics for 1.1+

| Metric | MICA baseline | Comparison condition |
| --- | --- | --- |
| Application bytes | emit raw image, isolate code from data | same algorithms, same optimization objective |
| Retired instructions | reference trace / RTL retirement counter | same application and input |
| Fetch bytes | halfwords accepted by instruction memory | equivalent flash/RAM timing |
| Data bus beats | completed read/write transactions | same memory type and cache configuration |
| Area | LUTs, FFs, BRAM or standard cells | same FPGA/process and synthesis setup |
| Speed | placed Fmax and cycles per task | compare completed work per second |
| Energy | measured joules/task after idle subtraction | equal voltage, temperature and workload |
| Sleep cost | µA in real idle state and wake latency | equal peripheral configuration |

Record all of these before calling an architecture superior. An RV32EC core such as Ibex is a useful comparison. For microcontroller energy, ULPMark-style active/idle workloads are more appropriate than a maximum-MHz contest.

## Failure criteria

Treat an architecture idea as unsuccessful if it wins instruction count but loses total energy on representative workload families, if state/decoder overhead wipes out the register-file savings, or if its interrupt latency becomes unacceptable for motor-control loops. Document negative results. They are still engineering results.
