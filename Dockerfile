FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["sh","-c","gunicorn -b 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 120 app:app"]
