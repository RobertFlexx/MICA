# Execution mode

The r2 implementations execute in one machine mode. All firmware shares CSR and
memory access; user/supervisor modes, an MPU and virtual memory are absent. CSR
rules still distinguish writable, read-only and reserved addresses, and invalid
accesses fault. T permits one active trap handler at a time.

The demonstration scheduler preserves task registers and switches trusted
machine-code tasks. It provides a context-switch example without a protection
boundary between those tasks. Protected execution would add privilege state, CSR and
memory checks to both implementations, together with fault tests.
