# cinegraph dev tasks. Run `make check` before committing.
PY := .venv/bin/python
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy

.PHONY: check test test-site lint typecheck fmt install-dev

check: lint typecheck test test-site  ## lint + type-check + tests (the pre-commit gate)

test:
	$(PY) -m pytest -q

# The Quartz-side plugin tests (the data-index emitter). Fails loudly rather than skipping
# when site deps are absent: a silently-skipped emitter test is how the indexes went missing
# in the first place.
test-site:
	@test -d site/node_modules || { \
	  echo "✗ site/node_modules missing — run: cd site && npm ci"; exit 1; }
	cd site && npx tsx --test plugins/cinegraph-views/*.test.js

lint:
	$(RUFF) check scripts/

typecheck:
	$(MYPY) scripts/

fmt:  ## apply ruff's safe autofixes (imports, etc.) — does NOT reformat code
	$(RUFF) check scripts/ --fix

install-dev:
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt
