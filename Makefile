# RailData - common tasks. Override e.g. `make daily DATE=2026-04-27`.
PY        ?= python
START     ?= 2026-03-02
END       ?= 2026-04-26
DATE      ?= 2026-04-27
DATA_DIR  ?= data
export RAILDATA_DATA_DIR := $(abspath $(DATA_DIR))
export RAILDATA_DUCKDB   := $(abspath $(DATA_DIR))/warehouse/raildata.duckdb

.PHONY: install lint format test run daily dbt-build dbt-docs report clean

install:            ## install the package and dev tools
	$(PY) -m pip install -e ".[dev]"

lint:               ## ruff lint + format check
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check --fix .

test:               ## unit + end-to-end tests (runs dbt on a temp dir)
	pytest -q

run:                ## backfill START..END (generate, ingest, dbt build)
	raildata --data-dir $(DATA_DIR) run --start $(START) --end $(END) --metrics-out docs/run_metrics.json

daily:              ## one daily run (idempotent: safe to re-run)
	raildata --data-dir $(DATA_DIR) run --date $(DATE)

dbt-build:          ## dbt build on the existing bronze data (all history)
	cd dbt && dbt build --profiles-dir .

dbt-docs:
	cd dbt && dbt docs generate --profiles-dir .

report:             ## render charts into docs/charts
	raildata --data-dir $(DATA_DIR) report --out docs/charts

clean:
	rm -rf $(DATA_DIR) dbt/target dbt/logs .pytest_cache .ruff_cache
