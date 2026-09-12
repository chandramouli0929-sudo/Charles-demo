.PHONY: install setup run-ui run-api test lint typecheck clean docker-up docker-down

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

setup: install
	cp -n .env.example .env || true
	@echo "✅ Setup complete. Edit .env with your API key."

# ── Run ────────────────────────────────────────────────────────────────────────
run-ui:
	streamlit run ui/streamlit_app.py

run-api:
	uvicorn reference_app.url_shortener.main:app --reload --port 8000

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# ── Quality ────────────────────────────────────────────────────────────────────
lint:
	ruff check app/ ui/ reference_app/ tests/

lint-fix:
	ruff check --fix app/ ui/ reference_app/ tests/

typecheck:
	mypy app/ reference_app/ --ignore-missing-imports

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-url-shortener:
	pytest reference_app/url_shortener/tests/ -v

test-cov:
	pytest tests/ --cov=app --cov=reference_app --cov-report=html

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -f *.db
