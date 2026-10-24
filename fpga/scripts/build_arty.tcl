# Vivado batch flow for Arty A7-100 rev D/E. Run from the repository root.
# Build the ROM with scripts/build_firmware.py first.
set root [file normalize [file join [file dirname [info script]] ../..]]
set out [file join $root build fpga]
file mkdir $out
set firmware selftest32
set mica2 0
if {$argc > 1} { error "Usage: vivado ... -tclargs selftest32|peripherals32|mica2_short32" }
if {$argc == 1} { set firmware [lindex $argv 0] }
if {$firmware ni {selftest32 peripherals32 mica2_short32}} { error "Unsupported board firmware: $firmware" }
if {$firmware eq "mica2_short32"} { set mica2 1 }
set rom [file join $root build firmware ${firmware}.bin]
if {![file exists $rom]} { error "Build firmware first: python3 scripts/build_firmware.py --tools build" }
set memfile [file join $out program.mem32]
exec python3 [file join $root toolchain bin2mem8.py] $rom $memfile --width 32 --pad-bytes 4096
create_project -force mica_arty $out -part xc7a100tcsg324-1
set_property include_dirs [list [file join $root isa generated]] [current_fileset]
read_verilog -sv [list [file join $root rtl mica_core_txn.sv] [file join $root rtl mica_soc.sv] [file join $root rtl mica_uart_tx.sv] [file join $root rtl mica_crc_mmio.sv] [file join $root boards arty_a7 mica_arty_a7.sv]]
read_verilog [list [file join $root rtl verilog mica_sram_txn.v] [file join $root rtl verilog mica_sync_fifo.v] [file join $root rtl verilog mica_uart_rx.v] [file join $root rtl verilog mica_uart_tx_portable.v]]
read_vhdl -vhdl2008 [file join $root rtl vhdl mica_crc32.vhd]
read_vhdl -vhdl2008 [list [file join $root rtl vhdl mica_event_counter.vhd] [file join $root rtl vhdl mica_watchdog.vhd]]
read_xdc [file join $root boards arty_a7 arty_a7.xdc]
set_property top mica_arty_a7 [current_fileset]
set_property generic [list "INIT_FILE=\"$memfile\"" MICA2=$mica2 TRAP=1 PERF=1 UART_RX=1 CRC_ENABLE=1] [current_fileset]
synth_design -top mica_arty_a7 -part xc7a100tcsg324-1
report_utilization -file [file join $out synthesis-utilization.rpt]
write_checkpoint -force [file join $out synthesized.dcp]
opt_design
place_design
phys_opt_design
route_design
report_timing_summary -file [file join $out timing.rpt]
report_utilization -file [file join $out implementation-utilization.rpt]
report_drc -file [file join $out drc.rpt]
write_checkpoint -force [file join $out routed.dcp]
set paths [get_timing_paths -max_paths 1 -nworst 1 -setup]
if {[llength $paths] == 0} { error "No setup timing paths; inspect clock constraints" }
if {[get_property SLACK [lindex $paths 0]] < 0} { error "Setup timing failed; no bitstream written" }
set hold_paths [get_timing_paths -max_paths 1 -nworst 1 -hold]
if {[llength $hold_paths] > 0 && [get_property SLACK [lindex $hold_paths 0]] < 0} { error "Hold timing failed" }
write_bitstream -force [file join $out mica_arty.bit]
