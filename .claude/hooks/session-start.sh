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

# Only run in Claude Code on the web (remote) sessions.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

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
  uv run prek install --hook-type pre-commit --hook-type commit-msg
else
  echo "Git hooks already installed; ensuring they are up to date..."
  uv run prek install --hook-type pre-commit --hook-type commit-msg
fi

echo "Pre-commit hooks verified and installed."
