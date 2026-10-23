.PHONY: install hooks fmt lint typecheck test check

install:  ## create .venv and install all dependencies from uv.lock
	uv sync

hooks:  ## install the leak-guard git hooks (Gate 1); run once per clone
	uv run pre-commit install

fmt:  ## rewrite files: format + auto-fix lint
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## check formatting and lint, change nothing
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov=mind --cov-report=term-missing

check: lint typecheck test  ## everything CI runs
