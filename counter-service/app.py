from fastapi import FastAPI

app = FastAPI()

# "база" балансів
balances = {}

@app.post("/update")
def update_balance(data: dict):
    user_id = data["user_id"]
    amount = data["amount"]

    if user_id not in balances:
        balances[user_id] = 0

    balances[user_id] += amount

    print("Updated balances:", balances)

    return {"balance": balances[user_id]}


@app.get("/balance/{user_id}")
def get_balance(user_id: int):
    return {"balance": balances.get(user_id, 0)}


@app.get("/balances")
def get_all_balances():
    return balances
