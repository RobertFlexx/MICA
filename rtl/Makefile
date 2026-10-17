# Simulation helpers. Needs Icarus Verilog, vvp, Python3 and built mica-as.
IVERILOG ?= iverilog
VVP ?= vvp
PYTHON ?= python3
ASM ?= ../build/mica-as
SV = mica_core.sv mica_soc.sv mica_uart_tx.sv

.PHONY: sim sim32 sim64 sim-flow32 sim-flow64 clean

sim: sim32

sim32:
	$(ASM) --xlen 32 ../examples/arithmetic32.mica -o program.bin
	$(PYTHON) ../toolchain/bin2mem8.py program.bin program.mem8
	$(IVERILOG) -g2012 -s tb_mica -o mica_sim $(SV) tb_mica.sv
	$(VVP) mica_sim

sim64:
	$(ASM) --xlen 64 ../examples/arithmetic64.mica -o program.bin
	$(PYTHON) ../toolchain/bin2mem8.py program.bin program.mem8
	$(IVERILOG) -g2012 -s tb_mica -Ptb_mica.XLEN=64 -o mica_sim $(SV) tb_mica.sv
	$(VVP) mica_sim

sim-flow32:
	$(ASM) --xlen 32 --flow ../examples/flow_copy32.mica -o program_flow.bin
	$(PYTHON) ../toolchain/bin2mem8.py program_flow.bin program_flow.mem8
	$(IVERILOG) -g2012 -s tb_flow -o mica_flow_sim $(SV) tb_flow.sv
	$(VVP) mica_flow_sim

sim-flow64:
	$(ASM) --xlen 64 --flow ../examples/flow_copy64.mica -o program_flow.bin
	$(PYTHON) ../toolchain/bin2mem8.py program_flow.bin program_flow.mem8
	$(IVERILOG) -g2012 -s tb_flow -Ptb_flow.XLEN=64 -o mica_flow_sim $(SV) tb_flow.sv
	$(VVP) mica_flow_sim

clean:
	rm -f mica_sim mica_flow_sim program.bin program.mem8 program_flow.bin program_flow.mem8
