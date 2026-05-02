from fastapi import FastAPI
import requests
import time

app = FastAPI()

LOGGING_URL = "http://logging-service:8081"
COUNTER_URL = "http://counter-service:8082"

# метрики
logging_time = 0
counter_time = 0


@app.post("/transaction")
def create_transaction(data: dict):
    global logging_time, counter_time

    user_id = data["user_id"]
    amount = data["amount"]

    transaction = {
        "transaction_id": str(time.time()),
        "user_id": user_id,
        "amount": amount
    }

    # logging-service
    start = time.time()
    requests.post(f"{LOGGING_URL}/log", json=transaction)
    logging_time += time.time() - start

    # counter-service
    start = time.time()
    response = requests.post(f"{COUNTER_URL}/update", json=transaction)
    counter_time += time.time() - start

    balance = response.json()["balance"]

    return {
        "transaction_id": transaction["transaction_id"],
        "balance": balance
    }


@app.get("/user/{user_id}")
def get_user(user_id: int):
    balance = requests.get(f"{COUNTER_URL}/balance/{user_id}").json()
    transactions = requests.get(f"{LOGGING_URL}/transactions/{user_id}").json()

    return {
        "balance": balance["balance"],
        "transactions": transactions
    }


@app.get("/accounts")
def get_accounts():
    return requests.get(f"{COUNTER_URL}/balances").json()


@app.get("/metrics")
def get_metrics():
    return {
        "logging_time": logging_time,
        "counter_time": counter_time
    }
