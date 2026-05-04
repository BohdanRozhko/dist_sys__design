from fastapi import FastAPI
import requests
import time
import uuid

app = FastAPI()

LOGGING_SERVICES = [
    "http://logging1:8081",
    "http://logging2:8081",
    "http://logging3:8081"
]

COUNTER_SERVICE = "http://counter:8082"

logging_time = 0
counter_time = 0


# ----------------------------
# CREATE TRANSACTION
# ----------------------------
@app.post("/transaction")
def transaction(data: dict):
    global logging_time, counter_time

    tx_id = str(uuid.uuid4())

    payload = {
        "transaction_id": tx_id,
        "user_id": data["user_id"],
        "amount": data["amount"]
    }

    # ----------------------------
    # LOGGING (FAILSAFE)
    # ----------------------------
    start = time.time()

    log_success = False
    for service in LOGGING_SERVICES:
        try:
            requests.post(
                f"{service}/log",
                json=payload,
                timeout=2
            )
            log_success = True
            break
        except Exception:
            continue

    logging_time += time.time() - start

    # ----------------------------
    # COUNTER SERVICE
    # ----------------------------
    start = time.time()

    try:
        res = requests.post(
            f"{COUNTER_SERVICE}/update",
            json=payload,
            timeout=2
        )
        balance = res.json().get("balance")
    except Exception:
        balance = None

    counter_time += time.time() - start

    return {
        "transaction_id": tx_id,
        "balance": balance,
        "logging_saved": log_success
    }


# ----------------------------
# GET TRANSACTIONS (FAILSAFE)
# ----------------------------
@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    last_error = None

    for service in LOGGING_SERVICES:
        try:
            res = requests.get(
                f"{service}/transactions/{user_id}",
                timeout=2
            )
            return res.json()
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "transactions": [],
        "error": "All logging services are down",
        "details": last_error
    }


# ----------------------------
# GET ACCOUNTS
# ----------------------------
@app.get("/accounts")
def accounts():
    try:
        res = requests.get(
            f"{COUNTER_SERVICE}/accounts",
            timeout=2
        )
        return res.json()
    except Exception as e:
        return {
            "error": "Counter service unavailable",
            "details": str(e)
        }


# ----------------------------
# METRICS
# ----------------------------
@app.get("/metrics")
def metrics():
    return {
        "logging_time": logging_time,
        "counter_time": counter_time
    }
