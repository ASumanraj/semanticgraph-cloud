FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
CMD ["python", "-c", "import time; print('API Mock Booting'); time.sleep(3600)"]
