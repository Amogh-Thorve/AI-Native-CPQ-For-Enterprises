# ============================================================
# CPQ Platform - Developer Workflow Commands
# ============================================================
# Usage: make <target>
# Windows users without make: run the commands in each target manually.

.PHONY: help db-up db-down migrate rollback backend frontend install demo

help:
	@echo "CPQ Platform Developer Commands:"
	@echo ""
	@echo "  make db-up       Start PostgreSQL via Docker Compose"
	@echo "  make db-down     Stop PostgreSQL container"
	@echo "  make migrate     Run all pending Alembic migrations"
	@echo "  make rollback    Roll back the last Alembic migration"
	@echo "  make backend     Start the FastAPI dev server (requires db-up)"
	@echo "  make frontend    Start the Next.js dev server"
	@echo "  make install     Install all Python + Node dependencies"
	@echo "  make demo        Migrate, seed demo data, start backend + frontend"
	@echo ""

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	cd backend && python -m alembic upgrade head

rollback:
	cd backend && python -m alembic downgrade -1

backend:
	python backend/run.py

frontend:
	cd frontend && npm run dev

install:
	pip install -r backend/requirements.txt
	cd frontend && npm install

demo: db-up migrate
	python scripts/seed_dev.py
	$(MAKE) -j2 backend frontend
