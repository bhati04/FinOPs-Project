.PHONY: help up down logs check backend-check frontend-check compose-check

help:
	@echo "CloudWise development commands"
	@echo "  make up             Start the local stack"
	@echo "  make down           Stop the local stack"
	@echo "  make logs           Follow service logs"
	@echo "  make check          Run all Milestone 0 checks"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

backend-check:
	docker compose run --rm backend sh -c "ruff format --check . && ruff check . && mypy src && pytest"

frontend-check:
	docker compose run --rm frontend-dev sh -c "npm run format:check && npm run lint && npm run typecheck && npm test -- --run && npm run build"

compose-check:
	docker compose config --quiet

check: compose-check backend-check frontend-check

