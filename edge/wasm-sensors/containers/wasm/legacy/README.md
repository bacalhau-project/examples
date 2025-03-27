# Legacy Implementation

This directory contains an initial implementation attempt to support updating configuration files at runtime using WebAssembly (WASM). The implementation included several components:

- `config-reader`: Attempted to read configuration files at runtime
- `config-updater`: Attempted to update configuration files at runtime
- `dir-lister`: Utility for listing directory contents
- `sqs-publisher`: Message publishing functionality

## Why This Approach Was Abandoned

This implementation was ultimately not pursued due to limitations with our current wazero-based executor. Instead of runtime configuration updates, we have opted to update the job configuration directly. This approach provides better reliability and simpler implementation while achieving the same goals.

The code in this directory is preserved for reference and historical context.
