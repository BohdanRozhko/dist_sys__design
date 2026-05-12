FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn requests psycopg2-binary hazelcast-python-client
COPY app.py .
EXPOSE 8082
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8082"]
