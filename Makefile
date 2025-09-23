SHELL := /usr/bin/bash
PY := python3
UI := ui
MOCK := tools/mock-server

.PHONY: help
help:
	@echo "Targets: test, py, ui, ui-test, ui-build, ui-serve, diagram, docs, clean"

## Python
.PHONY: py
py:
	$(PY) -m pip install -U pip
	pip install -r requirements.txt
	pytest -q backtest/tests

.PHONY: test
test: py ui-test

## UI
.PHONY: ui
ui:
	cd $(MOCK) && npm i
	cd $(UI) && npm ci || npm i
	-@kill $$(cat $(MOCK)/.mock.pid) 2>/dev/null || true
	cd $(MOCK) && (node server.mjs & echo $$! > .mock.pid)
	sleep 1
	cd $(UI) && npm run dev

.PHONY: ui-build
ui-build:
	cd $(UI) && npm ci || npm i
	cd $(UI) && npm run build

.PHONY: ui-serve
ui-serve:
	cd $(UI) && npm run preview

.PHONY: ui-test
ui-test:
	cd $(MOCK) && npm i
	cd $(UI) && npm ci || npm i
	-@kill $$(cat $(MOCK)/.mock.pid) 2>/dev/null || true
	cd $(MOCK) && (node server.mjs & echo $$! > .mock.pid)
	sleep 1
	cd $(UI) && npm run test:unit
	cd $(UI) && npx playwright install --with-deps
	cd $(UI) && npm run build
	cd $(UI) && npm run test:e2e
	-@kill $$(cat $(MOCK)/.mock.pid) 2>/dev/null || true

## Docs (Mermaid)
.PHONY: diagram
diagram:
	bash .github/scripts/render_mermaid.sh docs/system_diagram.md

.PHONY: docs
docs: diagram

.PHONY: clean
clean:
	rm -rf docs-diagrams/out $(MOCK)/.mock.pid
