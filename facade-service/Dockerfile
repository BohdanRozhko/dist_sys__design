FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn requests hazelcast-python-client python-consul psycopg2-binary
COPY app.py .
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
