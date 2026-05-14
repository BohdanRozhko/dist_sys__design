from fastapi import FastAPI
import psycopg2
import hazelcast
import threading
import time
import os
import socket
import consul

app = FastAPI()

HOSTNAME     = socket.gethostname()
SERVICE_PORT = int(os.getenv("SERVICE_PORT", 8082))
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
                name="counter-service",
                service_id=f"counter-{HOSTNAME}",
                address=HOSTNAME,
                port=SERVICE_PORT,
                tags=["counter"],
                check=consul.Check.http(
                    f"http://{HOSTNAME}:{SERVICE_PORT}/health",
                    interval="10s",
                    timeout="5s",
                    deregister="30s",
                ),
            )
            print(f"✅ Registered counter-service [{HOSTNAME}:{SERVICE_PORT}] in Consul", flush=True)
            return
        except Exception as e:
            print(f"❌ Consul register attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    print("❌ FAILED to register in Consul", flush=True)


# ─── DB ───────────────────────────────────────────────────────────────────────
def connect_db():
    for i in range(20):
        try:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "postgres"),
                database=os.getenv("DB_NAME", "bank"),
                user=os.getenv("DB_USER", "user"),
                password=os.getenv("DB_PASSWORD", "password"),
            )
            conn.autocommit = True
            print("✅ DB connected", flush=True)
            return conn
        except Exception as e:
            print(f"❌ DB attempt {i+1}: {e}", flush=True)
            time.sleep(2)
    raise Exception("Cannot connect to DB")


conn = connect_db()
cur  = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        user_id INT PRIMARY KEY,
        balance INT DEFAULT 0
    )
""")
print("✅ DB INIT DONE", flush=True)


# ─── HAZELCAST QUEUE (config from Consul KV) ─────────────────────────────────
def connect_hazelcast():
    members_raw = read_kv("hazelcast/members", default="hazelcast1:5701,hazelcast2:5701,hazelcast3:5701")
    queue_name  = read_kv("mq/queue_name",     default="transactions-queue")
    members = [m.strip() for m in members_raw.split(",")]

    print(f"🔌 Connecting to Hazelcast: {members}", flush=True)
    for i in range(15):
        try:
            client = hazelcast.HazelcastClient(cluster_members=members)
            q = client.get_queue(queue_name).blocking()
            print(f"✅ Connected to Hazelcast queue [{queue_name}]", flush=True)
            return client, q
        except Exception as e:
            print(f"❌ Hazelcast attempt {i+1}: {e}", flush=True)
            time.sleep(3)
    raise Exception("Cannot connect to Hazelcast")


# ─── CONSUMER THREAD ─────────────────────────────────────────────────────────
def process_queue(q):
    print("🚀 CONSUMER STARTED", flush=True)
    while True:
        try:
            data = q.take()  # blocking
            print(f"📥 RECEIVED FROM QUEUE: {data}", flush=True)
            user_id = data["user_id"]
            amount  = data["amount"]
            msg     = data.get("msg", "")
            cur.execute("""
                INSERT INTO accounts (user_id, balance)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET balance = accounts.balance + EXCLUDED.balance
                RETURNING balance
            """, (user_id, amount))
            balance = cur.fetchone()[0]
            print(f"✅ UPDATED: user={user_id}, msg={msg}, amount={amount}, balance={balance}", flush=True)
        except Exception as e:
            print(f"❌ CONSUMER ERROR: {e}", flush=True)
            time.sleep(1)


# ─── API ──────────────────────────────────────────────────────────────────────
@app.get("/accounts")
def get_accounts():
    try:
        cur.execute("SELECT user_id, balance FROM accounts ORDER BY user_id")
        return {str(r[0]): r[1] for r in cur.fetchall()}
    except Exception as e:
        print(f"❌ GET accounts: {e}", flush=True)
        return None


@app.get("/health")
def health():
    return {"status": "ok", "instance": HOSTNAME}


# ─── STARTUP ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    print("🔥 counter-service STARTUP", flush=True)
    time.sleep(5)
    register_self()
    _, q = connect_hazelcast()
    t = threading.Thread(target=process_queue, args=(q,), daemon=True)
    t.start()
    print("🔥 CONSUMER THREAD STARTED", flush=True)
