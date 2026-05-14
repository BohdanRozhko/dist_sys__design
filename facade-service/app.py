from fastapi import FastAPI
import requests
import random
import uuid
import os
import time
import socket
import hazelcast
import consul

app = FastAPI()

HOSTNAME = socket.gethostname()
SERVICE_PORT = int(os.getenv("SERVICE_PORT", 8080))
CONSUL_HOST  = os.getenv("CONSUL_HOST", "consul")
CONSUL_PORT  = int(os.getenv("CONSUL_PORT", 8500))

# Aggregated timing for metrics
metrics = {
    "logging_time": 0.0,
    "counter_time": 0.0,
    "logging_calls": 0,
    "counter_calls": 0,
}

# ─── CONSUL CLIENT ────────────────────────────────────────────────────────────
def get_consul():
    return consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)


# ─── READ CONFIG FROM CONSUL KV ──────────────────────────────────────────────
def read_kv(key, default=None, retries=15):
    """Read a key from Consul KV store with retries."""
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
    print(f"⚠️  KV [{key}] not found, using default: {default}", flush=True)
    return default


# ─── SERVICE DISCOVERY ───────────────────────────────────────────────────────
def discover(service_name):
    """Return list of healthy service URLs from Consul."""
    c = get_consul()
    try:
        _, services = c.health.service(service_name, passing=True)
        urls = []
        for svc in services:
            addr = svc["Service"]["Address"] or svc["Node"]["Address"]
            port = svc["Service"]["Port"]
            urls.append(f"http://{addr}:{port}")
        print(f"📡 discover [{service_name}]: {urls}", flush=True)
        return urls
    except Exception as e:
        print(f"❌ discover [{service_name}] error: {e}", flush=True)
        return []


# ─── REGISTER SELF IN CONSUL ─────────────────────────────────────────────────
def register_self():
    c = get_consul()
    for i in range(15):
        try:
            c.agent.service.register(
                name="facade-service",
                service_id=f"facade-{HOSTNAME}",
                address=HOSTNAME,
                port=SERVICE_PORT,
                tags=["facade"],
                check=consul.Check.http(
                    f"http://{HOSTNAME}:{SERVICE_PORT}/health",
                    interval="10s",
                    timeout="5s",
                    deregister="30s",
                ),
            )
            print(f"✅ Registered facade-service [{HOSTNAME}:{SERVICE_PORT}] in Consul", flush=True)
            return
        except Exception as e:
            print(f"❌ Consul register attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    print("❌ FAILED to register in Consul", flush=True)


# ─── HAZELCAST (config from Consul KV) ───────────────────────────────────────
def connect_hazelcast():
    members_raw = read_kv("hazelcast/members", default="hazelcast1:5701,hazelcast2:5701,hazelcast3:5701")
    members = [m.strip() for m in members_raw.split(",")]
    queue_name = read_kv("mq/queue_name", default="transactions-queue")

    print(f"🔌 Connecting to Hazelcast: {members}", flush=True)
    for i in range(15):
        try:
            client = hazelcast.HazelcastClient(cluster_members=members)
            print("✅ Connected to Hazelcast", flush=True)
            q = client.get_queue(queue_name).blocking()
            print(f"✅ Queue [{queue_name}] ready", flush=True)
            return client, q
        except Exception as e:
            print(f"❌ Hazelcast attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    raise Exception("Cannot connect to Hazelcast")


# ─── STARTUP ─────────────────────────────────────────────────────────────────
hz_client = None
queue = None


@app.on_event("startup")
def startup():
    global hz_client, queue
    time.sleep(5)  # let Consul and Hazelcast come up
    register_self()
    hz_client, queue = connect_hazelcast()
    print("🚀 facade-service ready", flush=True)


# ─── POST /transaction ────────────────────────────────────────────────────────
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

    # 1. Log to a random healthy logging-service (HTTP)
    log_success = False
    services = discover("logging-service")
    random.shuffle(services)
    for svc in services:
        try:
            t0 = time.time()
            requests.post(f"{svc}/log", json=payload, timeout=2)
            elapsed = time.time() - t0
            metrics["logging_time"] += elapsed
            metrics["logging_calls"] += 1
            print(f"✅ logged via {svc} in {elapsed:.3f}s", flush=True)
            log_success = True
            break
        except Exception as e:
            print(f"❌ logging via {svc} failed: {e}", flush=True)

    if not log_success:
        print("⚠️  ALL logging services failed", flush=True)

    # 2. Put into Hazelcast Queue (async)
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

    return {"status": "accepted", "tx_id": tx_id, "msg": payload["msg"], "logging": log_success}


# ─── GET /accounts ────────────────────────────────────────────────────────────
@app.get("/accounts")
def accounts():
    services = discover("counter-service")
    if not services:
        return None
    svc = random.choice(services)
    try:
        t0 = time.time()
        res = requests.get(f"{svc}/accounts", timeout=2)
        print(f"✅ counter in {time.time()-t0:.3f}s", flush=True)
        return res.json()
    except Exception as e:
        print(f"❌ counter failed: {e}", flush=True)
        return None


# ─── GET /transaction ─────────────────────────────────────────────────────────
@app.get("/transaction")
def get_transaction(user_id: int = None):
    logs = None
    log_svcs = discover("logging-service")
    if log_svcs:
        svc = random.choice(log_svcs)
        try:
            url = f"{svc}/transactions/{user_id}" if user_id else f"{svc}/transactions/all"
            logs = requests.get(url, timeout=2).json()
        except Exception as e:
            print(f"❌ log read: {e}", flush=True)

    balance = None
    cnt_svcs = discover("counter-service")
    if cnt_svcs:
        svc = random.choice(cnt_svcs)
        try:
            balance = requests.get(f"{svc}/accounts", timeout=2).json()
        except Exception as e:
            print(f"❌ balance read: {e}", flush=True)

    return {"logs": logs, "balance": balance}


# ─── GET /metrics ─────────────────────────────────────────────────────────────
@app.get("/metrics")
def get_metrics():
    return {
        "logging_time": round(metrics["logging_time"], 4),
        "logging_calls": metrics["logging_calls"],
        "counter_time": round(metrics["counter_time"], 4),
        "counter_calls": metrics["counter_calls"],
    }


# ─── GET /health ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "instance": HOSTNAME}
