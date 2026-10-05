.PHONY: dev down logs

dev:
	docker compose up -d --build

down: 
	docker compose down

logs: 
	docker compose logs -f backend
	