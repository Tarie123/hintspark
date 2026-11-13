FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD exec gunicorn -b :$PORT -w 2 --timeout 60 wsgi:app
