run:
	uv run trimmy

render-playground:
	uv run trimmy-render-playground

render-snapshots:
	uv run trimmy-render-playground --snapshot-dir .codex/render-playground

install:
	uv sync --group dev
	uv run prek install --hook-type pre-commit --hook-type commit-msg

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check
	uv run pytest
