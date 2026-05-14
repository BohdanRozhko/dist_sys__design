# Lab 5 — Service Discovery та Config Server на базі Consul

## Архітектура

```
                    ┌─────────────────────────────────┐
                    │         CONSUL  :8500           │
                    │  Service Registry + KV Config   │
                    │  KV: hazelcast/members          │
                    │  KV: hazelcast/map_name         │
                    │  KV: mq/queue_name              │
                    └──────────────┬──────────────────┘
        register/discover          │
  facade:8080 ── logging1/2/3:8081 ── counter:8082
      │                    │                  │
      │── HTTP /log ───────► Hazelcast Map    │
      │── queue.put() ──────────────────────► queue.take()
                [Hazelcast Queue]             PostgreSQL
```

**Ключові особливості:**
- Жодних статичних адрес у коді — всі через Consul Service Discovery
- Конфіги Hazelcast і MQ у Consul KV Store
- Consul Health Checks — автоматичне виключення нездорових інстансів

## Сервіси та порти

| Сервіс           | Порт  | Опис                          |
|------------------|-------|-------------------------------|
| consul           | 8500  | Service Registry + KV + UI    |
| facade-service   | 8080  | Єдина точка входу, MQ producer|
| logging-service-1| 8081  | Hazelcast Map                 |
| logging-service-2| 8083  | Hazelcast Map                 |
| logging-service-3| 8084  | Hazelcast Map                 |
| counter-service  | 8082  | MQ consumer, PostgreSQL       |
| hazelcast1-3     | 5701+ | Distributed Queue + Map       |
| postgres         | 5432  | Баланси                       |

## Запуск

```bash
git checkout micro_consul
docker compose up --build
```

Зачекайте ~15 секунд. Consul UI: http://localhost:8500/ui

## Consul KV

```bash
# Перевірити всі ключі:
curl http://localhost:8500/v1/kv/?recurse

# Healthy інстанси logging-service:
curl "http://localhost:8500/v1/health/service/logging-service?passing"
```

## Тестування

```bash
# 10 транзакцій
python transactions_sent.py

# GET балансу
curl http://localhost:8080/accounts

# Метрики
curl http://localhost:8080/metrics

# Навантажувальний тест
python client.py
```

## Тест відмовостійкості

```bash
# Зупинити logging2 — Consul через 15с покаже critical, трафік йде на logging1/3
docker stop logging2

# Зупинити counter — POST без помилок (черга), GET -> null
docker pause counter

# Відновити counter — вичитає накопичені повідомлення
docker unpause counter
```
