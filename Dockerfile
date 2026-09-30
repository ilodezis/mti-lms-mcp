FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py test_lms.py ./

EXPOSE 8030

CMD ["python", "server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8030"]
