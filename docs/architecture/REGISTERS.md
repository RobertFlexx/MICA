# Scalar registers

| Name | Alias | Assembly ABI |
| --- | --- | --- |
| x0 | zero | hardwired zero |
| x1..x4 | a 0..a 3 | arguments, caller saved; result in x1 |
| x5 | t0, fp | callee saved |
| x6 | lr | call return link; save around nested calls |
| x7 | sp | descending stack, restore on return |
| x8..x11 | none | X only, caller saved |
| x12..x15 | none | X only, callee saved |

Short formats address x0..x7. Long formats address x0..x15 only when X is
present. The physical transactional register array has eight entries without
X and sixteen with X. Reset clears registers and initializes SP according to
the configured RAM size. There are no register windows or hidden bank state.

F loads can commit a destination and a distinct base update together. Stores
update only the base. x0 ignores writes but never suppresses memory access.
The register array uses asynchronous reads and up to two commit writes; it
is not a block RAM macro. Read/mux replication and flip-flop costs must be
assessed from the synthesis result for the chosen parameters.
