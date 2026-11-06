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

eval:
	.venv/bin/python eval/run_eval.py --method b1

predict:
	@echo "make predict: not implemented yet" && exit 1

api:
	.venv/bin/python -m uvicorn watchkeeper.api.app:app --host 127.0.0.1 --port 8000

web:
	cd web && npm install --no-audit --no-fund && npm run dev

demo:
	@echo "make demo: not implemented yet" && exit 1

test:
	.venv/bin/python -m pytest tests
