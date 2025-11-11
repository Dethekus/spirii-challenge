PYTHON ?= python3

.PHONY: test format lint clean-dist

test:
	$(PYTHON) -m pytest tests

format:
	$(PYTHON) -m black src tests

lint:
	$(PYTHON) -m ruff check src tests

clean-dist:
	rm -f dist/*.zip

