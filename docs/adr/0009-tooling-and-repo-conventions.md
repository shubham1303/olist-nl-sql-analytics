# 0009. Tooling and repository conventions

- Status: Accepted
- Date: 2026-09-23

## Context

The tooling should be fast, reproducible and identical locally (Windows) and in CI
(Linux), with a minimum of moving parts.

## Decision

**Python backend (`backend/`):**
- Python **3.13**, which matches the Lambda runtime we'll deploy.
- **uv** for environments, locking (`uv.lock` is committed) and running tools.
- **ruff** for linting and formatting, **mypy** in strict mode, and **pytest** with
  markers:
  - `integration`: requires Docker Postgres.
  - `live`: requires AWS credentials and costs money. Always opt-in.
  - The default run excludes both.
- Runtime dependencies stay small and pure-Python where possible. Lambda artifacts are
  built for the Lambda platform, never from Windows site-packages.

**Frontend (`frontend/`):** Vite, React, TypeScript (strict), **oxlint** (the current
Vite template's default linter, run with `--deny-warnings`), Vitest and React Testing
Library, with **npm** and a committed `package-lock.json`. Node 24 LTS.

**Infrastructure (`infra/`):**
- Terraform, one root configuration (`infra/main`) with files split by concern.
- No custom module hierarchy.
- One `dev` environment.
- S3 remote state with native lockfile (`use_lockfile`, no DynamoDB), set up in
  Phase 7.

**CI:** GitHub Actions `ci.yml`, which runs on push and pull requests:
- backend lint, format check, type check and unit tests
- frontend lint, type check, test and build
- `terraform fmt -check` and `validate`

Integration tests join CI in Phase 1. Deploys use GitHub OIDC, with no long-lived AWS
keys (Phase 8).

**Task running:** commands are documented in the README and run directly through `uv`
and `npm`. There's no Makefile, because `make` isn't available on the Windows dev
machine.

**Line endings:** LF for everything except Windows-only scripts, enforced with
`.gitattributes`.

## Consequences

- One lockfile per ecosystem makes local and CI environments reproducible.
- Contributors need `uv`, Node 24 LTS (pinned in `.nvmrc`), Docker and Terraform ≥ 1.10
  installed.
