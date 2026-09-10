.PHONY: dev test test-frontend test-backend lint security compose-config migrate production-image

dev:
	python scripts/dev_setup.py
	docker compose --env-file .env.local up --build --wait

test: test-frontend test-backend

test-frontend:
	npm run test:frontend
	npm run build

test-backend:
	cd backend && python -m pytest

lint:
	npm run lint
	cd backend && python -m ruff check app tests alembic
	cd backend && python -m ruff format --check app tests alembic

security:
	python scripts/scan_secrets.py
	npm run security:deps
	docker run --rm -v "$(CURDIR):/repo:ro" zricethezav/gitleaks:v8.30.0 dir /repo --config /repo/.gitleaks.toml --redact --no-banner --exclude node_modules --exclude dist --exclude .git --exclude .verification

compose-config:
	docker compose --env-file .env.local config --quiet

migrate:
	docker compose --env-file .env.local exec backend alembic upgrade head

production-image:
	docker build --tag tandem:production .
