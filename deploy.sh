#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

docker compose build

docker compose up -d

docker compose exec frases_web python manage.py collectstatic --noinput
