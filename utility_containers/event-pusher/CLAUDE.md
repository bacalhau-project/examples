# CLAUDE.md - Build and Style Guide

## Build & Run Commands
- Build TypeScript WASM: `bun run build`
- Build Rust WASM: `cargo build --target wasm32-wasi --release`
- Build container: `./build_container.sh`
- Local debug server: `cd local_debug && ./start.sh`
- Run local tests: `bun test` (if tests are added)
- Format TypeScript: `bun run fmt` (consider adding)
- Format Rust: `cargo fmt` (consider adding)
- Lint TypeScript: `bun run lint` (consider adding)

## Code Style Guidelines
- Consistent naming: camelCase for TypeScript, snake_case for Rust
- Validate inputs with specific validation functions
- Error handling: throw descriptive errors in TypeScript, return Result in Rust
- Use classes for data structures in TypeScript
- Maintain identical function signatures between TypeScript and Rust versions
- Comments for complex logic or non-obvious behaviors
- Format code before committing

## Constants
- Define constant arrays and values at module level
- Emoji set should remain in sync between implementations