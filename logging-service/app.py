from fastapi import FastAPI
import hazelcast
import requests
import os
import socket
import time

app = FastAPI()

# ---------------- CONFIG ----------------
CONFIG_URL = os.getenv("CONFIG_URL", "http://config-server:8000")

HOSTNAME = socket.gethostname()
SERVICE_URL = f"http://{HOSTNAME}:8081"

# ---------------- REGISTER ----------------
def register():
    print(f"🔄 [{HOSTNAME}] registering logging-service...", flush=True)

    for i in range(10):
        try:
            requests.post(
                f"{CONFIG_URL}/register",
                json={"name": "logging", "url": SERVICE_URL},
                timeout=2
            )
            print(f"✅ REGISTERED [{HOSTNAME}] -> {SERVICE_URL}", flush=True)
            return
        except Exception as e:
            print(f"❌ register attempt {i+1} failed: {e}", flush=True)
            time.sleep(2)

    print("❌ FAILED TO REGISTER", flush=True)


# ---------------- HAZELCAST ----------------
print("🔌 Connecting to Hazelcast...", flush=True)

client = hazelcast.HazelcastClient(
    cluster_members=[
        "hazelcast1:5701",
        "hazelcast2:5701",
        "hazelcast3:5701"
    ]
)

transactions = client.get_map("transactions").blocking()

print("✅ Connected to Hazelcast map", flush=True)


# ---------------- STARTUP ----------------
@app.on_event("startup")
def startup():
    print(f"🚀 STARTING logging-service [{HOSTNAME}]", flush=True)
    register()


# ---------------- LOG TRANSACTION ----------------
@app.post("/log")
def log_transaction(data: dict):
    try:
        tx_id = data["transaction_id"]
        transactions.put(tx_id, data)
        print(f"📥 [{HOSTNAME}] LOGGED: {data}", flush=True)
        return {"status": "ok", "instance": HOSTNAME}
    except Exception as e:
        print(f"❌ [{HOSTNAME}] LOG ERROR: {e}", flush=True)
        return {"error": "log failed"}


# ---------------- GET USER TRANSACTIONS ----------------
@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    try:
        result = []
        print(f"📤 [{HOSTNAME}] fetching transactions for user {user_id}", flush=True)
        for _, tx in transactions.entry_set():
            if tx["user_id"] == user_id:
                result.append(tx)
        print(f"✅ [{HOSTNAME}] found {len(result)} transactions", flush=True)
        return result
    except Exception as e:
        print(f"❌ [{HOSTNAME}] READ ERROR: {e}", flush=True)
        return []


# ---------------- HEALTH ----------------
@app.get("/health")
def health():
    return {"status": "ok", "instance": HOSTNAME}
