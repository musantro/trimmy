#!/bin/bash
# SessionStart hook: verify and install the project's pre-commit (prek) git hooks.
#
# Trimmy uses `prek` (a pre-commit-compatible runner, shipped as a dev
# dependency) with hooks defined in .pre-commit-config.yaml:
#   - pre-commit stage: ruff, ruff-format, ty
#   - commit-msg stage: commitizen
#
# This hook ensures the dev dependencies are installed and that the git hooks
# are wired into .git/hooks, so commits made during the session are linted and
# their messages validated.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# uv installs to ~/.local/bin, which isn't always on PATH inside the hook.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found on PATH; cannot install pre-commit hooks." >&2
  exit 1
fi

# Install dev dependencies (prek, ruff, ty, commitizen, pytest, ...).
echo "Syncing dev dependencies with uv..."
uv sync --group dev

# Verify the git hooks are installed; install any that are missing.
# `prek install` is idempotent, so this both verifies and (re)installs.
hooks_dir="$(git rev-parse --git-path hooks)"
need_install=0
for hook in pre-commit commit-msg; do
  if [ ! -f "$hooks_dir/$hook" ]; then
    echo "Git $hook hook not installed."
    need_install=1
  fi
done

if [ "$need_install" -eq 1 ]; then
  echo "Installing prek git hooks..."
else
  echo "Git hooks already installed; ensuring they are up to date..."
fi
uv run prek install --hook-type pre-commit --hook-type commit-msg

# `prek install` only writes the .git/hooks shims; the hook repos themselves are
# cloned lazily on first run. Pre-fetch and build the hook environments now so
# that network/egress problems surface at session start instead of silently
# breaking the developer's first commit.
echo "Preparing hook environments (prek install-hooks)..."
if uv run prek install-hooks; then
  echo "Pre-commit hooks verified, installed, and ready to run."
else
  status=$?
  {
    echo ""
    echo "WARNING: pre-commit hook environments could not be prepared (exit ${status})."
    echo "The git hook shims are installed, but the hook repos failed to download."
    echo "In hosted Codex sessions this may happen when an egress network policy"
    echo "blocks github.com. Commits will fail the hooks until the environment's"
    echo "network policy allows github.com, or the config is switched to local tooling."
    echo "See \"${PREK_HOME:-$HOME/.cache/prek}/prek.log\" for the exact errors."
  } >&2
  # Don't abort the session over linting tooling; just make the failure loud.
fi
