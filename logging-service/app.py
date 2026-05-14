from fastapi import FastAPI
import hazelcast
import os
import socket
import time
import consul

app = FastAPI()

HOSTNAME     = socket.gethostname()
SERVICE_PORT = int(os.getenv("SERVICE_PORT", 8081))
CONSUL_HOST  = os.getenv("CONSUL_HOST", "consul")
CONSUL_PORT  = int(os.getenv("CONSUL_PORT", 8500))


# ─── CONSUL ──────────────────────────────────────────────────────────────────
def get_consul():
    return consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)


def read_kv(key, default=None, retries=15):
    c = get_consul()
    for i in range(retries):
        try:
            _, data = c.kv.get(key)
            if data and data["Value"]:
                val = data["Value"].decode()
                print(f"📖 KV [{key}] = {val}", flush=True)
                return val
        except Exception as e:
            print(f"⚠️  KV read attempt {i+1} [{key}]: {e}", flush=True)
        time.sleep(2)
    return default


def register_self():
    c = get_consul()
    for i in range(15):
        try:
            c.agent.service.register(
                name="logging-service",
                service_id=f"logging-{HOSTNAME}",
                address=HOSTNAME,
                port=SERVICE_PORT,
                tags=["logging"],
                check=consul.Check.http(
                    f"http://{HOSTNAME}:{SERVICE_PORT}/health",
                    interval="10s",
                    timeout="5s",
                    deregister="30s",
                ),
            )
            print(f"✅ Registered logging-service [{HOSTNAME}:{SERVICE_PORT}] in Consul", flush=True)
            return
        except Exception as e:
            print(f"❌ Consul register attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    print("❌ FAILED to register in Consul", flush=True)


# ─── HAZELCAST (config from Consul KV) ───────────────────────────────────────
transactions = None


def connect_hazelcast():
    global transactions
    members_raw = read_kv("hazelcast/members", default="hazelcast1:5701,hazelcast2:5701,hazelcast3:5701")
    map_name    = read_kv("hazelcast/map_name", default="transactions")
    members = [m.strip() for m in members_raw.split(",")]

    print(f"🔌 Connecting to Hazelcast: {members}", flush=True)
    for i in range(15):
        try:
            client = hazelcast.HazelcastClient(cluster_members=members)
            transactions = client.get_map(map_name).blocking()
            print(f"✅ Connected to Hazelcast map [{map_name}]", flush=True)
            return client
        except Exception as e:
            print(f"❌ Hazelcast attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    raise Exception("Cannot connect to Hazelcast")


# ─── STARTUP ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    print(f"🚀 STARTING logging-service [{HOSTNAME}]", flush=True)
    time.sleep(4)
    register_self()
    connect_hazelcast()


# ─── POST /log ────────────────────────────────────────────────────────────────
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


# ─── GET /transactions/{user_id} ─────────────────────────────────────────────
@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    try:
        result = []
        for _, tx in transactions.entry_set():
            if tx["user_id"] == user_id:
                result.append(tx)
        print(f"✅ [{HOSTNAME}] found {len(result)} txs for user {user_id}", flush=True)
        return result
    except Exception as e:
        print(f"❌ [{HOSTNAME}] READ ERROR: {e}", flush=True)
        return []


# ─── GET /health ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "instance": HOSTNAME}
