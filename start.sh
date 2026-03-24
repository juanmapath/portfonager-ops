#!/bin/bash
# 1. Aplicar migraciones
python manage.py migrate

# 2. Recolectar archivos estáticos para Whitenoise
python manage.py collectstatic --no-input

# 3. Ejecutar configuración de schedules (si existe el comando)
python manage.py setup_botops_schedules

# 4. Iniciar el worker de qcluster en segundo plano
python manage.py qcluster &

# 5. Iniciar gunicorn en primer plano
echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}
