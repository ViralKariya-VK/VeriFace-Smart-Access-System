#!/bin/sh
set -e
python manage.py migrate --noinput

# Exactly ONE worker process: the camera readers, recognition pipelines and the
# Arduino connection are in-process singletons. Concurrency comes from threads
# (each live MJPEG viewer holds one).
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 --threads 16 --worker-class gthread \
    --timeout 120 \
    --access-logfile -
