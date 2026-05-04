import requests
import time

BASE_URL = "http://localhost:8080/transaction"
ACCOUNTS_URL = "http://localhost:8080/accounts"

print("\n=== SENDING TRANSACTIONS ===")

success = 0

for i in range(1, 11):
    try:
        res = requests.post(BASE_URL, json={
            "user_id": 1,
            "amount": 1,
            "msg": f"msg{i}"
        }, timeout=5)

        if res.status_code == 200:
            print(f"msg{i} ->", res.json())
            success += 1
        else:
            print(f"msg{i} FAILED:", res.status_code, res.text)

    except Exception as e:
        print(f"msg{i} ERROR:", e)

    time.sleep(0.3)

print("\nSUCCESS:", success, "/ 10")

print("\n=== FINAL BALANCE CHECK ===")

try:
    res = requests.get(ACCOUNTS_URL, timeout=5)
    print("Balances:", res.json())
except Exception as e:
    print("ERROR:", e)
