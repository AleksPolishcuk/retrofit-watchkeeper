PY ?= python3
PACK ?=

.PHONY: setup setup-pack data bank model eval report levels predict api web demo test results

setup:
	$(PY) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev,api]"

setup-pack:
	@test -n "$(PACK)" || (echo "usage: make setup-pack PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026" && exit 1)
	.venv/bin/python -m pip install -e "$(PACK)" --no-deps

data:
	@test -n "$(PACK)" || (echo "usage: make data PACK=/path/to/RETROFIT_AI_PARTICIPANTS_2026" && exit 1)
	scripts/link_data.sh "$(PACK)"

eval:
	.venv/bin/python eval/run_eval.py --method wk

bank:
	.venv/bin/python scripts/make_bank.py --out bank

model:
	.venv/bin/python eval/train_model.py --fit train --out models/wk.joblib
	.venv/bin/python eval/train_model.py --fit train+tune+dev --out models/wk_final.joblib

report:
	.venv/bin/python eval/run_report.py --model models/wk.joblib

levels:
	.venv/bin/python eval/run_levels.py --model models/wk.joblib --sets tune dev9

predict:
	.venv/bin/python -m watchkeeper.predict --assets PUMP-10 PUMP-11 PUMP-12 --model models/wk_final.joblib --out submission/predictions_test.csv

api:
	.venv/bin/python -m uvicorn watchkeeper.api.app:app --host 127.0.0.1 --port 8000

web:
	cd web && npm install --no-audit --no-fund && npm run dev

demo:
	@echo "make demo: not implemented yet" && exit 1

test:
	.venv/bin/python -m pytest tests
