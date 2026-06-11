install:
	uv sync --group dev
	uv run pre-commit install --hook-type commit-msg
