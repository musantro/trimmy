run:
	uv run trimmy


install:
	uv sync --group dev
	uv run prek install --hook-type pre-commit --hook-type commit-msg

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run ty check
	uv run python -m pytest
