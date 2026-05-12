from fastapi import FastAPI
import psycopg2
import hazelcast
import threading
import requests
import time
import os
import socket

app = FastAPI()

# ---------------- CONFIG ----------------
CONFIG_URL = os.getenv("CONFIG_URL", "http://config-server:8000")
HOSTNAME = socket.gethostname()
SERVICE_URL = f"http://{HOSTNAME}:8082"

# ---------------- REGISTER ----------------
def register():
    print("🔄 registering counter-service...", flush=True)
    for i in range(10):
        try:
            requests.post(
                f"{CONFIG_URL}/register",
                json={"name": "counter", "url": SERVICE_URL},
                timeout=2
            )
            print(f"✅ REGISTERED counter [{HOSTNAME}] -> {SERVICE_URL}", flush=True)
            return
        except Exception as e:
            print(f"❌ register attempt {i+1} failed: {e}", flush=True)
            time.sleep(2)
    print("❌ FAILED TO REGISTER counter", flush=True)


# ---------------- DB ----------------
def connect_db():
    for i in range(20):
        try:
            connection = psycopg2.connect(
                host=os.getenv("DB_HOST", "postgres"),
                database=os.getenv("DB_NAME", "bank"),
                user=os.getenv("DB_USER", "user"),
                password=os.getenv("DB_PASSWORD", "password")
            )
            connection.autocommit = True
            print("✅ DB connected", flush=True)
            return connection
        except Exception as e:
            print(f"❌ DB connect attempt {i+1}: {e}", flush=True)
            time.sleep(2)
    raise Exception("Cannot connect to DB")


conn = connect_db()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    user_id INT PRIMARY KEY,
    balance INT DEFAULT 0
)
""")

print("✅ DB INIT DONE", flush=True)


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

print("✅ Connected to Hazelcast queue", flush=True)


# ---------------- CONSUMER ----------------
def process_queue():
    print("🚀 CONSUMER STARTED", flush=True)

    while True:
        try:
            # blocking take — waits until message arrives
            data = queue.take()

            print(f"📥 RECEIVED FROM QUEUE: {data}", flush=True)

            user_id = data["user_id"]
            amount = data["amount"]
            msg = data.get("msg", "")

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


# ---------------- API ----------------
@app.get("/accounts")
def get_accounts():
    try:
        cur.execute("SELECT user_id, balance FROM accounts ORDER BY user_id")
        rows = cur.fetchall()
        return {str(r[0]): r[1] for r in rows}
    except Exception as e:
        print(f"❌ GET accounts error: {e}", flush=True)
        return None


@app.get("/health")
def health():
    return {"status": "ok", "instance": HOSTNAME}


# ---------------- STARTUP ----------------
@app.on_event("startup")
def startup():
    print("🔥 counter-service STARTUP", flush=True)
    register()
    thread = threading.Thread(target=process_queue, daemon=True)
    thread.start()
    print("🔥 CONSUMER THREAD STARTED", flush=True)
