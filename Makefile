PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
BLACK := .venv/bin/black
MYPY := .venv/bin/mypy
PRE_COMMIT := .venv/bin/pre-commit
BANDIT := .venv/bin/bandit
PIP_AUDIT := .venv/bin/pip-audit
UVICORN := .venv/bin/uvicorn

.PHONY: run test coverage lint format typecheck docker-up docker-down security pre-commit

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(PYTEST)

coverage:
	$(PYTEST) --cov=app/services --cov=app/models --cov=app/utils --cov-report=term-missing --cov-report=xml --cov-fail-under=80

lint:
	$(RUFF) check .
	$(BLACK) --check .

format:
	$(BLACK) .
	$(RUFF) check . --fix

typecheck:
	$(MYPY) .

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

security:
	$(BANDIT) -r app
	$(PIP_AUDIT)

pre-commit:
	$(PRE_COMMIT) run --all-files
