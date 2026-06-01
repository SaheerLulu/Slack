#!/bin/sh
set -e

echo "Running database migrations…"
python manage.py migrate --noinput

echo "Collecting static files…"
python manage.py collectstatic --noinput

echo "Starting daphne on 0.0.0.0:${PORT:-8000}…"
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
