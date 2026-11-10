.PHONY: dev data down logs test eval

dev:
	docker compose up -d --build --wait

data:
	docker compose -f docker-compose.yml -f compose.host.yml up -d --wait postgres redis

down:
	docker compose down

logs:
	docker compose logs -f backend frontend caddy

test:
	cd backend && uv run python -m pytest -q

eval:
	cd backend && uv run python -m evals.run --live
