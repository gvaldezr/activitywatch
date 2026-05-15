# ActivityWatch: AI Agent Guide

ActivityWatch is a **privacy-focused automated time tracker** that records what you do across applications and browser tabs. This guide helps AI agents quickly understand the codebase and contribute effectively.

## Quick Facts

- **Purpose**: Privacy-centric lifedata collection with user-controlled storage
- **Architecture**: Modular monorepo with Python core + Rust server, multiple watchers
- **Languages**: Python (primary), Rust, TypeScript/Vue (UI)
- **Build System**: Make + Poetry (Python), Cargo (Rust)
- **Main Reference**: [docs.activitywatch.net](https://docs.activitywatch.net) and [architecture docs](https://activitywatch.readthedocs.io/en/latest/architecture.html)

## Core Modules (Submodules)

All modules are git submodules. Most projects use Make+Poetry for build, with equivalent Makefiles.

### Essential Modules

- **aw-core**: Data model (events, buckets, queries); the foundation for all other modules
- **aw-server-rust**: High-performance REST API server (primary production server)
- **aw-server** (Python): Reference server implementation; used in development/testing
- **aw-client**: Python client library; used by watchers and third-party tools to communicate with server
- **aw-watcher-window**: Tracks active application and window title
- **aw-watcher-afk**: Detects if user is away from keyboard (AFK) using input events

### UI & Cross-Platform

- **aw-qt**: Qt-based desktop UI (traditional cross-platform approach)
- **aw-tauri**: Tauri-based UI (lighter weight alternative, modern)

### Additional Modules (Optional)

- **aw-watcher-input**: Mouse/keyboard activity tracking (use `AW_EXTRAS=true` to include)
- **aw-notify**: Notification system
- **awatcher**: Linux/Wayland-compatible window watcher (Linux only)

## Build Commands

### Main Build
```bash
# Default build (Qt, all modules except extras)
make build

# Build with Tauri UI instead of Qt
TAURI_BUILD=true make build

# Build with optional extras (aw-notify, aw-watcher-input)
AW_EXTRAS=true make build

# Build without Rust server (skip compilation bottleneck in development)
SKIP_SERVER_RUST=true make build

# Build release version (optimized)
RELEASE=true make build
```

### Testing & Quality
```bash
# Run all tests in modules that have test targets
make test

# Lint code
make lint

# Type checking (mypy for Python modules)
make typecheck

# Package for distribution
make package
```

### Install from Source
See [installing-from-source](https://activitywatch.readthedocs.io/en/latest/installing-from-source.html) in the docs. Typically:
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
make build
```

## Data Model

- **Event**: A timestamped datum with properties (duration, category, title, etc.)
- **Bucket**: A named collection of events from a specific data source (e.g., "aw-watcher-window")
- **Query language**: ActivityWatch Query Language (AWL) for filtering and transforming event data
- References: [buckets-and-events docs](https://activitywatch.readthedocs.io/en/latest/buckets-and-events.html)

## Database Backends (Storage)

### SQLite (Default)
- **Use case**: Single-user deployments, development, local testing
- **Pros**: No setup, minimal dependencies, zero configuration
- **Cons**: Limited concurrency, file-based (no network access)
- **Setup**: Automatic (default storage backend)

### PostgreSQL (Robust)
- **Use case**: Multi-user, production deployments, high event volume
- **Pros**: Multi-user support, ACID transactions, connection pooling, cloud-ready
- **Cons**: Requires PostgreSQL 13+ server, additional setup
- **Setup**: See [PostgreSQL Migration Guide](./docs/migrating-to-postgres.md)
- **Deployment**: See [PostgreSQL Deployment Guide](./docs/deployment-postgres.md)
- **Rust Implementation**: See [Rust PostgreSQL Implementation](./docs/RUST_POSTGRES_IMPLEMENTATION.md)
- **Config**: `AW_STORAGE=postgres` + `DATABASE_URL` environment variable

**Switching backends:**
```bash
# Use SQLite (default)
aw-server

# Use PostgreSQL (Python)
export AW_STORAGE=postgres
export DATABASE_URL="postgresql://user:pass@host:5432/activitywatch"
aw-server

# Use PostgreSQL (Rust, requires --features postgres_support during build)
export DATABASE_URL="postgresql://user:pass@host:5432/activitywatch"
aw-server-rust
```

Both backends use the same data model and are interchangeable. Migration script available for SQLite → PostgreSQL conversion.

## Remote Deployments & Server Configuration

ActivityWatch servers now support configurable remote access via environment variables, enabling multi-machine deployments.

### Remote Server Setup

By default, aw-server listens only on `127.0.0.1` (localhost). To expose the server to remote machines:

```bash
# Listen on all network interfaces
export AW_SERVER_HOST=0.0.0.0
export AW_SERVER_PORT=5600
aw-server-rust

# Or with Python server
aw-server --host 0.0.0.0 --port 5600
```

**Important**: When exposing externally, use a reverse proxy with SSL/TLS termination and enable authentication:

```toml
# ~/.config/activitywatch/config.toml
address = "0.0.0.0"
port = 5600

[auth]
api_key = "your_secure_api_key"
```

### Remote Client Configuration

Configure aw-client to connect to a remote server:

```bash
# Environment variables (highest flexibility)
export AW_SERVER_HOST=your.server.com
export AW_SERVER_PORT=5600
export AW_SERVER_API_KEY=your_secure_api_key
aw-client heartbeat bucket_name '{"data": "value"}'

# Or CLI arguments
aw-client --host your.server.com --port 5600 --api-key your_key ...
```

### Security Recommendations

- ⚠️ **Always use a reverse proxy** (Nginx, Apache, Caddy) with SSL/TLS for external deployments
- ✅ **Enable API key authentication** in server config `[auth] api_key = "..."`
- ✅ **Use firewall rules** to restrict access
- ✅ **Keep ActivityWatch updated** for security patches

See [Remote Connections Guide](./docs/REMOTE_CONNECTIONS.md) for complete setup instructions, Docker examples, and security best practices.

### Environment Variables Reference

| Variable | Applies To | Purpose |
|----------|-----------|---------|
| `AW_SERVER_HOST` | Server & Client | Listening/connection address (default: `127.0.0.1`) |
| `AW_SERVER_PORT` | Server & Client | Listening/connection port (default: `5600`) |
| `AW_SERVER_API_KEY` | Client | API key for remote authentication |
| `AW_STORAGE` | Server | Backend: `peewee` (SQLite), `postgres`, or `memory` |
| `DATABASE_URL` | Server | PostgreSQL connection string when `AW_STORAGE=postgres` |
| `RUST_LOG` | Server | Rust logging level: `trace`, `debug`, `info`, `warn`, `error` |
| `AW_LOG_LEVEL` | Server | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Development Conventions

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
<type>[optional scope]: <description>

[optional body]
[optional footer]
```

**Types**: `feat`, `fix`, `chore`, `ci`, `docs`, `style`, `refactor`, `perf`, `test`

Examples:
- `feat: added ability to sort by duration`
- `fix: incorrect week number calculation (#407)`
- `docs: improved query documentation`

### Code Issues
- Use [issue templates](https://github.com/ActivityWatch/activitywatch/issues/new/choose) when filing bugs or features
- Look for labels like `good first issue` and `help wanted` for newcomer-friendly tasks
- Reference issues in commits: `fixes #123`

### Python Style
- Type hints with mypy
- Tests via pytest
- Module-level Makefiles follow the pattern: `lint`, `typecheck`, `test`, `package`, `build` targets

## When Working on Issues

1. **Understanding the domain**: Check module README.md files and relevant [architecture](https://activitywatch.readthedocs.io/en/latest/architecture.html) docs before coding
2. **Testing locally**: Always run `make test` in the affected module and `make build` to verify integration
3. **Watchers**: If adding a new watcher, follow the pattern in aw-watcher-window or aw-watcher-afk; new watchers should use aw-client to communicate with aw-server
4. **REST API**: API changes belong in aw-server (Python) and aw-server-rust (Rust); keep both in sync
5. **Dependencies**: Update poetry.lock after modifying pyproject.toml; be cautious with urllib3 (see pinned version)

## Common Gotchas

- **Submodules not initialized**: If module directories are empty, git submodule setup may be incomplete. Run `git submodule update --init --recursive`
- **Rust server builds slowly**: Use `SKIP_SERVER_RUST=true make build` in development for faster iteration
- **Pyinstaller hooks**: aw-server-rust has custom hooks in `pyinstaller-hooks-contrib`; don't ignore packaging failures silently
- **Python version**: Requires Python ≥3.8 and <3.14 (per pyproject.toml and pyinstaller constraints)
- **urllib3 version**: Pinned to <2; verify before upgrading dependencies

## Repository Links

- **Forum**: [forum.activitywatch.net](https://forum.activitywatch.net/)
- **Discord**: [discord.gg/vDskV9q](https://discord.gg/vDskV9q)
- **Roadmap**: [orgs/ActivityWatch/projects/2](https://github.com/orgs/ActivityWatch/projects/2)
- **Feature requests**: [Feature category on forum](https://forum.activitywatch.net/c/features)
- **Contributor stats**: [activitywatch.net/contributors](https://activitywatch.net/contributors/)

## Specialized Guides

For working on specific areas of ActivityWatch, see:
- **[Rust Development](./.github/copilot-instructions-rust.md)** — Building aw-server-rust, managing builds with `make aw-sync`, API consistency
- **[Watcher Development](./.aw-watcher-dev.md)** — Creating new watchers, project structure, integration patterns, platform-specific code

## Next Steps for AI Agents

1. **Documentation review**: Read [contributing guide](./CONTRIBUTING.md), [architecture docs](https://activitywatch.readthedocs.io/en/latest/architecture.html)
2. **Running locally**: `make build` and test in your environment to verify setup works
3. **PostgreSQL setup**: See [Phase 1-3 Summary](./docs/PHASE_1_2_SUMMARY.md) and [Phase 3 Integration](./docs/PHASE_3_INTEGRATION.md) for multi-backend support
4. **Issue-focused work**: When assigned an issue, check module READMEs for domain context, run tests, and verify no regressions
5. **Specialized tasks**: For Rust work, see the Rust guide; for new watchers, see the Watcher guide

## Database Implementation Status

**Phase 1 (Python)**: ✅ COMPLETE - PostgreSQL backend for aw-core  
**Phase 2 (Rust)**: ✅ COMPLETE - PostgreSQL backend for aw-server-rust  
**Phase 3 (Integration)**: ✅ COMPLETE - Worker integration and backend detection  
**Phase 4 (Testing)**: 📋 PENDING - Parametrized tests and CI/CD  

See [PHASE_1_2_SUMMARY.md](./docs/PHASE_1_2_SUMMARY.md) and [PHASE_3_INTEGRATION.md](./docs/PHASE_3_INTEGRATION.md) for details.

---

*Last updated: May 2026*
