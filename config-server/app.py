from fastapi import FastAPI
from collections import defaultdict

app = FastAPI()

registry = defaultdict(list)


@app.post("/register")
def register(data: dict):
    name = data["name"]
    url = data["url"]

    if url not in registry[name]:
        registry[name].append(url)

    print(f"[REGISTER] {name} -> {url}", flush=True)

    return {"status": "ok"}


@app.get("/services/{name}")
def get_service(name: str):
    services = registry.get(name, [])

    print(f"[DISCOVERY] {name} -> {services}", flush=True)

    return {
        "service": name,
        "instances": services
    }


@app.get("/services")
def list_all():
    return dict(registry)


@app.post("/reset")
def reset():
    registry.clear()
    print("🧹 registry cleared", flush=True)
    return {"ok": True}
