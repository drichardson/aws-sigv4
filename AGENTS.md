# Agents Guide

Read `DESIGN.md` first for the architecture, two-layer API, and credential chain.

## Development Commands

```sh
uv run pytest                            # run tests
uv run mypy src tests                    # type checking
uv run ruff format && uv run ruff check  # format and lint
```

## Conventions

- **Python 3.14+** — use modern syntax: `type` aliases, `match` statements.
- **Zero runtime dependencies** — stdlib only. Do not add any third-party
  runtime dependencies. Dev-only deps (pytest, mypy, ruff) are fine.
- **Sync-only** — credential fetching uses `urllib.request`. The signing
  itself is pure computation with no I/O.
- **Structural typing** — prefer `Protocol` over inheritance for interfaces
  (see `CredentialProvider`).
- **Immutable credentials** — `Credentials` is a frozen dataclass. Create
  a new instance on each refresh; never mutate in place.
- **Thread safety** — `RefreshableCredentials` uses `threading.Lock`. All
  mutations to `_credentials` must be inside the lock.
- **SPDX headers** — all source files start with the SPDX copyright and
  license identifier comments.

## When making changes always use Pull Requests

1. Create a branch
2. Push to a PR.

Don't push to main.
