import requests
import time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8080/transaction"

CLIENTS = 10
REQUESTS_PER_CLIENT = 10000


# метрики
logging_times = []
counter_times = []


def send_requests_same_user(user_id):
    global logging_times, counter_times

    for _ in range(REQUESTS_PER_CLIENT):
        start = time.time()

        requests.post(BASE_URL, json={
            "user_id": user_id,
            "amount": 1
        })

        end = time.time()

    return


def run_scenario_1():
    print("\n=== SCENARIO 1: 10 users, separate accounts ===")

    start_total = time.time()

    with ThreadPoolExecutor(max_workers=CLIENTS) as executor:
        executor.map(send_requests_same_user, range(1, 11))

    end_total = time.time()

    total_time = end_total - start_total
    total_requests = CLIENTS * REQUESTS_PER_CLIENT
    rps = total_requests / total_time

    print("\nRESULTS SCENARIO 1")
    print("Total time:", total_time)
    print("Total requests:", total_requests)
    print("Requests/sec:", rps)


def run_scenario_2():
    print("\n=== SCENARIO 2: 10 users, same account ===")

    start_total = time.time()

    with ThreadPoolExecutor(max_workers=CLIENTS) as executor:
        executor.map(lambda _: send_requests_same_user(1), range(10))

    end_total = time.time()

    total_time = end_total - start_total
    total_requests = CLIENTS * REQUESTS_PER_CLIENT
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
    print("\n=== SERVICE CONTRIBUTION (from facade) ===")

    metrics = requests.get("http://localhost:8080/metrics").json()

    print("Logging-service time:", metrics["logging_time"])
    print("Counter-service time:", metrics["counter_time"])


if __name__ == "__main__":
    run_scenario_1()
    run_scenario_2()

    check_final_state()
    get_facade_metrics()
