from fastapi import FastAPI

app = FastAPI()

# "база" в пам’яті
transactions = {}

@app.post("/log")
def log_transaction(data: dict):
    transaction_id = data["transaction_id"]
    transactions[transaction_id] = data

    print("Saved transaction:", data)
    return {"status": "ok"}


@app.get("/transactions/{user_id}")
def get_user_transactions(user_id: int):
    result = [
        tx for tx in transactions.values()
        if tx["user_id"] == user_id
    ]
    return result


@app.get("/transactions")
def get_all():
    return list(transactions.values())
