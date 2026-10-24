#!/usr/bin/env python3
"""Exercise peripheral parameter boundaries and reject invalid configurations."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, ok=True):
    result = subprocess.run(
        [str(x) for x in command], capture_output=True, text=True, timeout=30
    )
    if (result.returncode == 0) != ok:
        raise RuntimeError(f"{command}\n{result.stdout}{result.stderr}")
    return result


with tempfile.TemporaryDirectory(prefix="mica-params-") as temp:
    stage = Path(temp)
    cases = [
        ("mica_sync_fifo", ".DEPTH(0)", False),
        ("mica_sync_fifo", ".DEPTH(4),.COUNT_W(2)", False),
        ("mica_sync_fifo", ".DEPTH(3),.PTR_W(1)", False),
        ("mica_uart_rx", ".BAUD(0)", False),
        ("mica_uart_rx", ".DIVISOR(3)", False),
        ("mica_uart_rx", ".DIVISOR(16),.COUNT_W(3)", False),
        ("mica_uart_tx_portable", ".BAUD(0)", False),
        ("mica_uart_tx_portable", ".DIVISOR(16),.COUNT_W(3)", False),
        ("mica_uart_tx_portable", ".DIVISOR(1)", True),
        ("mica_spi_master", ".CLOCK_DIV(0)", False),
        ("mica_spi_master", ".CPHA(2)", False),
        ("mica_spi_master", ".CLOCK_DIV(8),.COUNT_W(2)", False),
        ("mica_spi_master", ".CLOCK_DIV(1)", True),
        ("mica_sram_txn", ".RAM_BYTES(6)", False),
        ("mica_sram_txn", ".DATA_W(16)", False),
        ("mica_sram_txn", ".RAM_BYTES(4)", True),
        ("mica_sram_txn", ".DATA_W(64),.RAM_BYTES(8)", True),
    ]
    for index, (name, params, valid) in enumerate(cases):
        source, binary = stage / "case.v", stage / "case.out"
        source.write_text(
            f"module test; {name} #({params}) dut(); initial begin #1; $finish; end endmodule\n"
        )
        run(
            [
                "iverilog",
                "-g2005",
                "-s",
                "test",
                "-o",
                binary,
                ROOT / f"rtl/verilog/{name}.v",
                source,
            ]
        )
        result = run(["vvp", binary], ok=valid)
        if not valid and "invalid" not in result.stdout + result.stderr:
            raise AssertionError(
                "invalid configuration did not report its parameter error"
            )
    for depth in (1, 16):
        binary = stage / "fifo"
        run(
            [
                "iverilog",
                "-g2005",
                "-s",
                "tb_mica_sync_fifo",
                f"-Ptb_mica_sync_fifo.DEPTH={depth}",
                "-o",
                binary,
                ROOT / "rtl/verilog/mica_sync_fifo.v",
                ROOT / "rtl/verilog/tb_mica_sync_fifo.v",
            ]
        )
        print(run(["vvp", binary]).stdout.strip())
    for divisor in (1, 3):
        binary = stage / "spi"
        run(
            [
                "iverilog",
                "-g2005",
                "-s",
                "tb_mica_spi_master",
                f"-Ptb_mica_spi_master.CLOCK_DIV={divisor}",
                "-o",
                binary,
                ROOT / "rtl/verilog/mica_spi_master.v",
                ROOT / "rtl/verilog/tb_mica_spi_master.v",
            ]
        )
        print(run(["vvp", binary]).stdout.strip())
print(f"PASS {len(cases)} HDL parameter configurations")
