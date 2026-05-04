from fastapi import FastAPI
import hazelcast
import uuid
import time

app = FastAPI()

client = hazelcast.HazelcastClient(
    cluster_members=[
        "hazelcast1:5701",
        "hazelcast2:5701",
        "hazelcast3:5701"
    ]
)

transactions = client.get_map("transactions").blocking()


@app.post("/log")
def log_transaction(data: dict):
    tx_id = data["transaction_id"]
    transactions.put(tx_id, data)
    print(f"LOGGED: {data}")
    return {"status": "ok"}


@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    result = []

    for _, tx in transactions.entry_set():
        if tx["user_id"] == user_id:
            result.append(tx)

    return result
