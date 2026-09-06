.PHONY: fmt lint test build

PYTHON ?= python3

fmt:
	$(PYTHON) -m py_compile src/tracker/*.py tests/*.py

lint:
	$(PYTHON) -m py_compile src/tracker/*.py tests/*.py

test:
	$(PYTHON) -m pytest -q

build:
	$(PYTHON) -m pip install -e ".[dev]"
