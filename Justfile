set shell := ["bash", "-uc"]
set dotenv-load := false

default:
    @just --list

bootstrap:
    @echo "→ Creating .venv-api with Python 3.11"
    cd app && uv sync --python 3.11
    @echo "✓ API venv ready. Run: just dev"

dev:
    @cd app && uv run --python 3.11 uvicorn jmb.main:app --host 127.0.0.1 --port 8768 --reload

health:
    @curl -s http://127.0.0.1:8768/api/health | python3 -m json.tool

clean-venvs:
    rm -rf app/.venv workers/*/.venv

clean-data:
    @echo "WARNING: deletes all jobs in ~/Library/Application Support/JustinsMagicMusicBox/"
    @read -p "Continue? [y/N] " ans && [ "$ans" = "y" ] && rm -rf ~/Library/Application\ Support/JustinsMagicMusicBox/ || echo "aborted"
