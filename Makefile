.PHONY: dev down logs test eval

dev:
	docker compose up -d --build

down: 
	docker compose down

logs: 
	docker compose logs -f backend

test:
	cd backend && uv run python -m pytest -q

eval:
	cd backend && uv run python -m evals.run --live
