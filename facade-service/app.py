from fastapi import FastAPI
import requests
import random
import uuid
import os
import time
import hazelcast

app = FastAPI()

CONFIG_URL = os.getenv("CONFIG_URL", "http://config-server:8000")

# Aggregated timing for metrics
metrics = {
    "logging_time": 0.0,
    "counter_time": 0.0,
    "logging_calls": 0,
    "counter_calls": 0,
}

# ---------------- HAZELCAST ----------------
def connect_hazelcast():
    for i in range(15):
        try:
            client = hazelcast.HazelcastClient(
                cluster_members=[
                    "hazelcast1:5701",
                    "hazelcast2:5701",
                    "hazelcast3:5701"
                ]
            )
            print("✅ Connected to Hazelcast", flush=True)
            return client
        except Exception as e:
            print(f"❌ Hazelcast connect attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    raise Exception("Cannot connect to Hazelcast")


hz_client = connect_hazelcast()
queue = hz_client.get_queue("transactions-queue").blocking()

print("✅ facade connected to Hazelcast queue", flush=True)


# ---------------- CONFIG SERVER ----------------
def get_service(name):
    try:
        res = requests.get(f"{CONFIG_URL}/services/{name}", timeout=2)
        instances = res.json().get("instances", [])
        print(f"📡 [{name}] instances: {instances}", flush=True)
        return instances
    except Exception as e:
        print(f"❌ CONFIG ERROR ({name}): {e}", flush=True)
        return []


# ---------------- POST /transaction ----------------
@app.post("/transaction")
def transaction(data: dict):
    tx_id = str(uuid.uuid4())

    payload = {
        "transaction_id": tx_id,
        "user_id": data["user_id"],
        "amount": data.get("amount", 0),
        "msg": data.get("msg", ""),
    }

    print(f"\n📥 NEW TRANSACTION: {payload}", flush=True)

    # 1. Send to a random logging-service instance (HTTP, synchronous)
    log_success = False
    services = get_service("logging")
    random.shuffle(services)

    for service in services:
        try:
            t0 = time.time()
            requests.post(f"{service}/log", json=payload, timeout=2)
            elapsed = time.time() - t0
            metrics["logging_time"] += elapsed
            metrics["logging_calls"] += 1
            print(f"✅ logged via {service} in {elapsed:.3f}s", flush=True)
            log_success = True
            break
        except Exception as e:
            print(f"❌ logging via {service} failed: {e}", flush=True)

    if not log_success:
        print("⚠️  ALL logging services failed", flush=True)

    # 2. Put into Hazelcast Queue for counter-service (async, non-blocking)
    try:
        t0 = time.time()
        queue.put(payload)
        elapsed = time.time() - t0
        metrics["counter_time"] += elapsed
        metrics["counter_calls"] += 1
        print(f"📤 queued to Hazelcast in {elapsed:.3f}s", flush=True)
    except Exception as e:
        print(f"❌ QUEUE ERROR: {e}", flush=True)
        return {"error": "queue failed", "tx_id": tx_id}

    return {
        "status": "accepted",
        "tx_id": tx_id,
        "msg": payload["msg"],
        "logging": log_success,
    }


# ---------------- GET /accounts ----------------
@app.get("/accounts")
def accounts():
    services = get_service("counter")

    if not services:
        print("❌ no counter services", flush=True)
        return {"error": "counter unavailable", "balances": None}

    service = random.choice(services)
    try:
        t0 = time.time()
        res = requests.get(f"{service}/accounts", timeout=2)
        elapsed = time.time() - t0
        print(f"✅ counter response in {elapsed:.3f}s: {res.json()}", flush=True)
        return res.json()
    except Exception as e:
        print(f"❌ counter failed: {e}", flush=True)
        return None


# ---------------- GET /transaction (alias for accounts + logs) ----------------
@app.get("/transaction")
def get_transaction(user_id: int = None):
    """Read logs from a random logging-service + balance from counter-service."""

    # Logs
    logs = None
    log_services = get_service("logging")
    if log_services:
        service = random.choice(log_services)
        try:
            if user_id is not None:
                res = requests.get(f"{service}/transactions/{user_id}", timeout=2)
            else:
                res = requests.get(f"{service}/transactions/all", timeout=2)
            logs = res.json()
        except Exception as e:
            print(f"❌ log read failed: {e}", flush=True)

    # Balance
    balance = None
    counter_services = get_service("counter")
    if counter_services:
        service = random.choice(counter_services)
        try:
            res = requests.get(f"{service}/accounts", timeout=2)
            balance = res.json()
        except Exception as e:
            print(f"❌ counter read failed: {e}", flush=True)

    return {"logs": logs, "balance": balance}


# ---------------- GET /metrics ----------------
@app.get("/metrics")
def get_metrics():
    return {
        "logging_time": round(metrics["logging_time"], 4),
        "logging_calls": metrics["logging_calls"],
        "counter_time": round(metrics["counter_time"], 4),
        "counter_calls": metrics["counter_calls"],
    }


# ---------------- GET /health ----------------
@app.get("/health")
def health():
    return {"status": "ok"}
