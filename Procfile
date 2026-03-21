web: python manage.py migrate && python manage.py setup_botops_schedules && gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}
worker: python manage.py qcluster
