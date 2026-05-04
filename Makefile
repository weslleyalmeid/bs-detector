.PHONY: setup install dev dev-backend dev-frontend eval analyze graph up down logs build

# ---------- Local (uv + npm) ----------

setup:
	uv venv backend/.venv
	uv pip install -r backend/requirements.txt --python backend/.venv/bin/python
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi
	cd frontend && npm install

install:
	uv pip install -r backend/requirements.txt --python backend/.venv/bin/python

dev:
	$(MAKE) -j 2 dev-backend dev-frontend

dev-backend:
	cd backend && ./.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8002

dev-frontend:
	cd frontend && npm run dev

eval:
	cd backend && ./.venv/bin/python evals/run_evals.py

graph:
	cd backend && ./.venv/bin/python print_graph.py

# ---------- Docker (clone & run) ----------

up:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example — set OPENAI_API_KEY before continuing."; fi
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build
