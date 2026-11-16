.PHONY: test lint

test:
	uv run --extra test python -m pytest tests/ -v

lint:
	uv run --with ruff ruff check custom_components/
