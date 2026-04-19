# Bilancio

Personal finance tracker. Ingests bank statement files, categorises transactions, and shows where money goes. Deployed to Azure Container Apps.

## Quick start (local)

```sh
cp .env.example .env
docker compose up
```

The API is at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

To run with the optional LLM service:

```sh
docker compose --profile llm up
```

## Development (without Docker)

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
# Install deps
uv sync --dev

# Apply migrations
uv run alembic upgrade head

# Start the API
uv run uvicorn bilancio.main:app --reload
```

## Testing

```sh
uv run pytest                                            # all tests + coverage
uv run pytest tests/unit                                 # unit tests only (fast, no DB)
uv run pytest tests/integration                          # integration tests (SQLite in-memory)
uv run pytest --cov=src --cov-report=html                # HTML coverage report
```

## Code quality

```sh
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

## Database migrations

```sh
uv run alembic upgrade head                              # apply all pending migrations
uv run alembic revision --autogenerate -m "<message>"   # generate a new migration
uv run alembic downgrade -1                              # roll back one step
```

## Docs

See [`docs/README.md`](docs/README.md) for the full documentation index.