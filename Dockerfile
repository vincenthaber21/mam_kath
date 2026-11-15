FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DEBUG=False SECRET_KEY=build python manage.py collectstatic --noinput
EXPOSE 8000
# One worker keeps a single copy of the model in memory; threads handle concurrent requests.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn eic_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120"]
