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

.PHONY: diagram
diagram:
	@NODE_PATH=$(npm root -g 2>/dev/null) node docs-diagrams/render.mjs docs/system_diagram.md
	@echo "PNG(s) in docs-diagrams/out/"
