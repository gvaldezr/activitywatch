# ActivityWatch Rust Development Guide

Guidance for working on Rust components of ActivityWatch, primarily **aw-server-rust** and related CLI tools.

## Rust Module Overview

### aw-server-rust
High-performance REST API server written in Rust. Can be built in two modes:
- **Full server** (default): Complete aw-server functionality, built with `make build`
- **aw-sync** (Tauri builds): Lightweight sync component for Tauri UI, built with `make aw-sync SKIP_WEBUI=true`

**Key details:**
- Uses Actix-web framework for REST API
- SQLite for data persistence  
- Custom pyinstaller hooks in `pyinstaller-hooks-contrib`
- Must keep API in sync with Python reference server (aw-server)

### Other Rust Components
- **awatcher**: Linux/Wayland-compatible window watcher (Linux only)
- CLI tools and utilities

## Build Commands

### Local Development

```bash
# Build aw-server-rust (full server)
cd aw-server-rust
make build

# Build for Tauri (aw-sync component only)
cd aw-server-rust
make aw-sync SKIP_WEBUI=true

# Build release version (optimized, slower)
cd aw-server-rust
RELEASE=true make build

# Skip entire Rust server in monorepo build (development iteration)
cd ..  # Root directory
SKIP_SERVER_RUST=true make build
```

### Testing & Quality

```bash
# Run Rust tests
cd aw-server-rust
cargo test

# Lint Rust code
cargo clippy

# Format code
cargo fmt

# Check dependencies for security issues
cargo audit
```

### Development Iteration Tips
- Use `SKIP_SERVER_RUST=true make build` from root when working on Python modules to avoid slow Rust recompilation
- When modifying Rust server, rebuild just that module: `cd aw-server-rust && cargo build`
- Use `cargo check` for fast syntax/type checking without full compilation
- Debug builds are much faster than release builds for iteration

## API Consistency

When modifying REST API endpoints in aw-server-rust:
1. **Update Python server first** if making breaking changes; sync Rust server afterward to match
2. **Keep endpoint signatures aligned**: Query parameters, request/response schemas
3. **Both servers must support the same buckets/events data model** (defined in aw-core)
4. **Check for Web UI dependencies**: API changes may require UI updates (aw-tauri, aw-qt)

## Common Tasks

### Adding a New Endpoint
1. Define request/response structures in Rust
2. Implement endpoint handler in aw-server-rust
3. Add corresponding endpoint to Python aw-server for feature parity
4. Test with both servers if integration is critical
5. Update Web UI if needed

### Working with SQLite
- Migrations handled via Diesel ORM or custom SQL
- Data persists in `~/.cache/activitywatch/aw-server-rust/` (Linux/macOS) or `%LOCALAPPDATA%\activitywatch\...` (Windows)
- For testing: Use in-memory databases or clean fixtures

### Fixing Pyinstaller Issues
- Rust binaries are statically linked, but check for native dependencies (OpenSSL, etc.)
- Custom hooks may be in `pyinstaller-hooks-contrib`; update if packaging fails
- Test packaged builds before release

## Performance Considerations

- Rust server is designed for **low memory footprint** and **fast API responses**
- Use async/await patterns for I/O operations (Actix is async)
- Profile with `perf` or `flamegraph` if performance regresses
- SQLite queries should have appropriate indexes for large datasets

## Environment Variables

- `DATABASE_URL`: SQLite database path (defaults to user cache directory)
- `SKIP_WEBUI`: Skip bundling web UI (useful for Tauri builds)
- `RELEASE`: Build release binary (optimized, longer compile time)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Slow builds | Use `SKIP_SERVER_RUST=true` when developing Python modules; use `cargo check` to validate without full build |
| Linking errors (OpenSSL, etc.) | Install system dependencies (libssl-dev on Linux); check feature flags in Cargo.toml |
| API mismatch with Python server | Cross-check endpoint definitions and data schemas; run integration tests |
| Packaging failures | Check pyinstaller-hooks-contrib for custom hooks; test packaged binary after rebuilding |

## References

- [Actix-web framework](https://actix.rs/)
- [Diesel ORM](https://diesel.rs/) (if used for database)
- [ActivityWatch architecture](https://activitywatch.readthedocs.io/en/latest/architecture.html)
- [Data model (buckets/events)](https://activitywatch.readthedocs.io/en/latest/buckets-and-events.html)
