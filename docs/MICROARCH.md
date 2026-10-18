# Reference core

The [microarchitecture guide](hardware/MICROARCHITECTURE.md) follows fetch, decode,
memory completion and retirement through `mica_core_txn`. Its [transactional
ports](hardware/MEMORY_INTERFACE.md) replace the original immediate-memory
assumption. [Pipeline work](hardware/PIPELINE.md) is tracked separately from this
implemented multicycle core.
