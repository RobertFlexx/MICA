# Hardware drawings

The [drawing index](hardware/DATAPATH.md) lists all 31 refreshed diagram paths:
the six 2.0 overviews, six elaborated transactional/SoC drawings and nineteen
existing top-level paths. Every drawing has DOT, SVG, PNG and PDF versions.

The [2.0 implementation guide](hardware/MICA2_IMPLEMENTATION.md) explains the
changed decode, stack operations and sleep/wake paths. Core and SoC inventories
come from Yosys elaboration with MICA2=1; a SHA-256 manifest detects stale sources
and rendered previews. Future multicore and split-slice proposals are explicitly
identified as research, with no corresponding production RTL claim.

These are architectural/connectivity drawings. Physical pin assignments and
the board vendor's electrical references are in
[board connections](hardware/BOARD_CONNECTIONS.md).
