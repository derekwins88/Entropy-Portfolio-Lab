SHELL := bash

.PHONY: dev ui mock test fmt type cov diagram
dev: mock ui
ui:
	cd ui && cp -n .env.example .env || true && npm i && npm run dev
mock:
	cd tools/mock-server && npm i && npm start
test:
	pytest -q
fmt:
	ruff check backtest --fix && black backtest
type:
	mypy backtest
cov:
	pytest -q --cov=backtest --cov-report=term-missing

IN ?= docs/system_diagram.md

.PHONY: diagram
diagram:
	@set -euo pipefail; \
	IN="$(IN)"; \
	OUTDIR=docs-diagrams/out; \
	CFG=docs-diagrams/puppeteer.json; \
	mkdir -p "$$OUTDIR"; \
	if ! command -v mmdc >/dev/null 2>&1; then \
	  npm i -g @mermaid-js/mermaid-cli@10.9.0; \
	fi; \
	awk '/^```mermaid/{flag=1; next} /^```/{flag=0} flag{print}' "$$IN" \
	| awk 'BEGIN{b=0} /^ *$$/{next} {print} END{}' \
	| csplit -s -f "$$OUTDIR/block-" -b "%02d.mmd" - '/^$$/+1' '{*}' || true; \
	shopt -s nullglob; \
	for f in "$$OUTDIR"/block-*.mmd; do \
	  png="$${f%.mmd}.png"; \
	  mmdc -i "$$f" -o "$$png" -p "$$CFG" --backgroundColor transparent; \
	  echo "Rendered $$png"; \
	done
