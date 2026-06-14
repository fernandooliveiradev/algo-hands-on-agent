#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "Instale o uv: https://docs.astral.sh/uv/"
  exit 1
fi

[ -f .env ] || cp .env.example .env
uv sync --extra dev
uv run aho doctor || true

echo "Edite .env, configure DEEPSEEK_API_KEY e execute:"
echo "  uv run aho setup --student-id maria --name 'Maria Silva'"
echo "  uv run aho chat --student-id maria"
echo ""
echo "Se esquecer qual ID usou: uv run aho students"
