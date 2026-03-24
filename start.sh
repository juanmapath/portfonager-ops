#!/bin/bash
# 1. Aplicar migraciones
echo "Running migrations..."
python manage.py migrate

# 2. Recolectar archivos estáticos
echo "Collecting static files..."
python manage.py collectstatic --no-input

# 3. Configurar schedules
echo "Setting up schedules..."
python manage.py setup_botops_schedules

# 4. Iniciar el worker de qcluster en segundo plano
echo "Starting Qcluster worker..."
python manage.py qcluster &

# 5. Iniciar gunicorn
echo "Starting Gunicorn server..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}
