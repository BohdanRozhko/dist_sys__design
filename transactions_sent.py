import requests
import time

BASE_URL = "http://localhost:8080/transaction"

print("=== SENDING 10 TRANSACTIONS ===\n")

for i in range(1, 11):
    res = requests.post(BASE_URL, json={
        "user_id": 1,
        "amount": 10,
        "msg": f"msg{i}"
    })
    print(f"msg{i} -> {res.json()}")
    time.sleep(0.2)

print("\n=== DONE ===")
print("\n=== CHECKING BALANCE ===")
time.sleep(1)
bal = requests.get("http://localhost:8080/accounts")
print("Balance:", bal.json())
