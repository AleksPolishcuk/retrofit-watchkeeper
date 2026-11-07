PY ?= python3
PACK ?=

.PHONY: alerts archive setup setup-pack data bank model eval report levels predict api web demo live-demo test results

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
	$(MAKE) -j2 api web

# Rewrites artifacts/alerts (what the interface shows): the nine public pumps from the model that was not fitted on them (needs models/wk.joblib, see
# `make model`), the three test pumps from the submitted CSV (no model, no test telemetry is read). The files are committed, so a fresh clone works without it.
alerts:
	.venv/bin/python eval/export_alerts.py --method wk --model models/wk.joblib
	.venv/bin/python scripts/export_submitted_alerts.py

# Keeps an immutable snapshot of artifacts/alerts per model version in artifacts/alerts_archive (a re-run overwrites the alert files, not the archive).
archive:
	.venv/bin/python -m watchkeeper.alerts.archive

# Replays the public validation pump PUMP-08 as raw messages (one per second) through the read-only ingest and the detector, writing
# artifacts/live/PUMP-08/state.json for the Overview page. It takes a few minutes; the first alert of this pump is at 10 Sep 09:33 UTC.
live-demo:
	rm -rf artifacts/live/PUMP-08
	.venv/bin/python -m watchkeeper.ingest.live --asset PUMP-08 --start 2025-09-08T00:00:00Z --end 2025-09-10T14:00:00Z --every 60 --fine-from 2025-09-10T08:30:00Z --fine-to 2025-09-10T10:00:00Z --fine-every 5

test:
	.venv/bin/python -m pytest tests
