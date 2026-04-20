#!/usr/bin/env bash
# test.sh — run the full quality suite: lint, type check, tests + coverage
#
# Usage:
#   ./scripts/test.sh           # full suite
#   ./scripts/test.sh --unit    # unit tests only (no DB, fast)
#   ./scripts/test.sh --int     # integration tests only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MODE="${1:-}"

run_lint() {
  echo "==> Lint (ruff check) ..."
  uv run ruff check src tests
  echo "==> Format check (ruff format --check) ..."
  uv run ruff format --check src tests
}

run_types() {
  echo "==> Type check (mypy) ..."
  uv run mypy src
}

run_tests() {
  local path="${1:-}"
  echo "==> Tests (pytest${path:+ $path}) ..."
  uv run pytest $path
}

case "$MODE" in
  --unit)
    run_tests "tests/unit"
    ;;
  --int)
    run_tests "tests/integration"
    ;;
  "")
    run_lint
    run_types
    run_tests ""
    echo ""
    echo "All checks passed."
    ;;
  *)
    echo "Usage: $0 [--unit | --int]"
    exit 1
    ;;
esac
