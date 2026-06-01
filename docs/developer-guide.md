# Developer Guide

## Environment Setup

1. Create a virtual environment.
2. Activate it.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables
Copy `.env.example` to `.env` and provide real values.

For Google Drive access, copy `service-account.example.json` to `service-account.json` locally and keep the real credential file out of git.

| Variable | Description | Default |
|---|---|---|
| OPENAI_API_KEY | OpenAI API key for summarization | Empty |
| GOOGLE_DRIVE_FOLDER_ID | Source folder ID for ingestion | Empty |
| GOOGLE_SERVICE_ACCOUNT_FILE | Service account JSON path | Empty |
| DOWNLOAD_DIR | Local download directory | downloads |
| OPENAI_MODEL | Responses API model | gpt-4o |
| MODEL_NAME | Reserved model alias | gpt-4o |
| SUMMARY_CHUNK_SIZE | Max tokens per chunk | 1200 |
| SUMMARY_CHUNK_OVERLAP | Overlap tokens between chunks | 150 |
| CACHE_DIR | Summary cache directory | cache |
| LOG_LEVEL | Logging level | INFO |
| CORS_ALLOWED_ORIGINS | Allowed CORS origins JSON array string | ["http://localhost","http://localhost:3000","http://127.0.0.1","http://127.0.0.1:3000"] |

## Running Locally

Start API:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run tests:
```bash
pytest
```

## Docker

```bash
docker-compose up --build
```

## Make Commands

- `make run`: run application
- `make test`: run pytest suite
- `make coverage`: run coverage target (80%+ on core layers)
- `make lint`: run Ruff and Black check
- `make format`: run Black + Ruff fix
- `make typecheck`: run MyPy
- `make security`: run Bandit + pip-audit
- `make pre-commit`: run all configured hooks
- `make docker-up`: start docker-compose
- `make docker-down`: stop docker-compose

## Code Quality Tooling

### Ruff
- Linting for pyflakes/pycodestyle/import ordering.
- Config: `ruff.toml`

Run:
```bash
make lint
```

### Black
- Formatting with line length 88.

Run:
```bash
make format
```

### MyPy
- Gradual typing focus on service/model/util layers.
- Config: `mypy.ini`

Run:
```bash
make typecheck
```

## Testing and Coverage

- Framework: Pytest
- Current suite: 33+ tests
- Coverage gate: 80%+ on:
  - `app/services`
  - `app/models`
  - `app/utils`

Run:
```bash
make coverage
```

## Security Scanning

### Bandit
```bash
bandit -r app
```

### pip-audit
```bash
pip-audit
```

Combined:
```bash
make security
```

## Pre-commit Hooks

Configured in `.pre-commit-config.yaml`:
- Black
- Ruff
- Ruff format
- MyPy

Run all hooks:
```bash
make pre-commit
```

## CI/CD Pipeline

GitHub Actions workflow: `.github/workflows/ci.yml`

Pipeline stages:
1. Checkout
2. Setup Python 3.12
3. Install dependencies
4. Run tests
5. Run Ruff
6. Run Black check
7. Run MyPy
8. Generate coverage (`coverage.xml`)

## Local Development Workflow

Recommended iteration loop:
1. `pip install -r requirements.txt`
2. `make format`
3. `make lint && make typecheck`
4. `make test`
5. `make pre-commit`

## Prompt Management

Prompts are file-driven (not hardcoded):
- `prompts/map_summary.txt`
- `prompts/reduce_summary.txt`

Managed by `PromptService` at runtime.

## Notes for Contributors

- Keep routes thin; push behavior into services.
- Preserve typed models across boundaries.
- Add tests for new service or route behavior.
- Prefer dashboard-first UX conventions used in the current product.
