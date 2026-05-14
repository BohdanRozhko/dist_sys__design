import requests
import time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8080/transaction"

CLIENTS = 10
REQUESTS_PER_CLIENT = 10000


def send_requests(user_id, requests_count):
    for _ in range(requests_count):
        requests.post(BASE_URL, json={
            "user_id": user_id,
            "amount": 1
        })


def run_scenario_1(clients, requests_per_client):
    print(f"\n=== SCENARIO 1: {clients} users, separate accounts ===")
    start = time.time()
    with ThreadPoolExecutor(max_workers=clients) as executor:
        executor.map(
            lambda uid: send_requests(uid, requests_per_client),
            range(1, clients + 1)
        )
    end = time.time()
    total_requests = clients * requests_per_client
    total_time = end - start
    rps = total_requests / total_time
    print("\nRESULTS SCENARIO 1")
    print("Total time:", total_time)
    print("Total requests:", total_requests)
    print("Requests/sec:", rps)


def run_scenario_2(clients, requests_per_client):
    print(f"\n=== SCENARIO 2: {clients} users, same account ===")
    start = time.time()
    with ThreadPoolExecutor(max_workers=clients) as executor:
        executor.map(
            lambda _: send_requests(1, requests_per_client),
            range(clients)
        )
    end = time.time()
    total_requests = clients * requests_per_client
    total_time = end - start
    rps = total_requests / total_time
    print("\nRESULTS SCENARIO 2")
    print("Total time:", total_time)
    print("Total requests:", total_requests)
    print("Requests/sec:", rps)


def check_final_state():
    print("\n=== FINAL CHECK ===")
    accounts = requests.get("http://localhost:8080/accounts").json()
    print("Balances:", accounts)


def get_facade_metrics():
    print("\n=== SERVICE CONTRIBUTION ===")
    metrics = requests.get("http://localhost:8080/metrics").json()
    print("Logging-service time:", metrics["logging_time"])
    print("Counter-service time:", metrics["counter_time"])


if __name__ == "__main__":
    run_scenario_1(CLIENTS, REQUESTS_PER_CLIENT)
    run_scenario_2(CLIENTS, REQUESTS_PER_CLIENT)
    check_final_state()
    get_facade_metrics()
