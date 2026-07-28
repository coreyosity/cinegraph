# cinegraph dev tasks. Run `make check` before committing.
PY := .venv/bin/python
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy

.PHONY: check test lint typecheck fmt install-dev

check: lint typecheck test  ## lint + type-check + tests (the pre-commit gate)

test:
	$(PY) -m pytest -q

lint:
	$(RUFF) check scripts/

typecheck:
	$(MYPY) scripts/

fmt:  ## apply ruff's safe autofixes (imports, etc.) — does NOT reformat code
	$(RUFF) check scripts/ --fix

install-dev:
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt
