#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f "manage.py" ]]; then
  echo "Erro: manage.py não encontrado em $PROJECT_DIR"
  exit 1
fi

if ! python -m spacy download de_core_news_lg; then
  echo "Aviso: falha ao baixar de_core_news_lg. Tentando de_core_news_md..."
  python -m spacy download de_core_news_md
fi

python manage.py makemigrations
python manage.py migrate

python manage.py test_pipeline
