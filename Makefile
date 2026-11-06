PY ?= python3
PACK ?=

.PHONY: setup setup-pack data eval predict api web demo test

setup:
	$(PY) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"

setup-pack:
	@test -n "$(PACK)" || (echo "usage: make setup-pack PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026" && exit 1)
	.venv/bin/python -m pip install -e "$(PACK)" --no-deps

data:
	@test -n "$(PACK)" || (echo "usage: make data PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026" && exit 1)
	scripts/link_data.sh "$(PACK)"

eval predict api web demo test:
	@echo "make $@: not implemented yet" && exit 1
