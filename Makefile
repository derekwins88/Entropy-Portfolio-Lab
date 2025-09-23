.PHONY: dev ui mock test fmt type cov
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
