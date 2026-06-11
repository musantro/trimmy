install:
	uv sync --group dev
	uv run prek install --hook-type commit-msg
