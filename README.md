# Lab 4 — Мікросервіси з Message Queue (Hazelcast Queue)

## Архітектура

```
          HTTP POST                  HTTP GET
Client ──────────────► facade ─────────────────► facade
                          │                         │
                    PUT to Queue            GET /accounts
                          │                         │
                    [Hazelcast Queue]        counter-service
                          │                    (PostgreSQL)
                    TAKE from Queue
                          │
                    counter-service ──► PostgreSQL
                          
facade ──► (random) ──► logging1 / logging2 / logging3
                           (Hazelcast Map — shared storage)

facade / counter ──► config-server (service registry)
```

**Ключова зміна від Lab 3:**  
POST-запит до `facade` тепер **не чекає** відповіді від `counter-service`.  
Замість прямого HTTP-виклику — повідомлення кладеться у **Hazelcast Queue**.  
`counter-service` вичитує черги у фоновому потоці та оновлює БД асинхронно.

---

## Запуск

```bash
docker compose up --build
```

Зачекайте ~15 секунд поки всі сервіси стартують і зареєструються.

---

## Сервіси та порти

| Сервіс         | Порт  | Опис                             |
|----------------|-------|----------------------------------|
| facade         | 8080  | Єдина точка входу для клієнта    |
| config-server  | 8000  | Реєстр сервісів                  |
| logging1       | 8081  | Логування транзакцій (інстанс 1) |
| logging2       | 8083  | Логування транзакцій (інстанс 2) |
| logging3       | 8084  | Логування транзакцій (інстанс 3) |
| counter        | 8082  | Баланси (consumer черги)         |
| hazelcast1     | 5701  | Hazelcast node 1                 |
| hazelcast2     | 5702  | Hazelcast node 2                 |
| hazelcast3     | 5703  | Hazelcast node 3                 |
| postgres       | 5432  | База даних балансів              |

---

## Тестування

### 1. Відправити 10 транзакцій (msg1–msg10)

```bash
python transactions_sent.py
```

або вручну:

```bash
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8080/transaction \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": 1, \"amount\": 10, \"msg\": \"msg$i\"}"
  echo ""
done
```

### 2. Перевірити баланс (GET)

```bash
curl http://localhost:8080/accounts
# {"1": 100}   # 10 транзакцій × 10 = 100
```

### 3. Перевірити реєстр сервісів

```bash
curl http://localhost:8000/services/logging
curl http://localhost:8000/services/counter
curl http://localhost:8000/services    # всі
```

### 4. Перевірити метрики facade

```bash
curl http://localhost:8080/metrics
```

---

## Тест відмовостійкості

### Крок 1 — зупинити counter-service

```bash
docker pause counter
```

### Крок 2 — відправити кілька транзакцій (вони йдуть у чергу без помилок)

```bash
for i in $(seq 11 15); do
  curl -s -X POST http://localhost:8080/transaction \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": 1, \"amount\": 10, \"msg\": \"msg$i\"}"
  echo ""
done
```

➡️ Усі запити повертають `"status": "accepted"` — без помилок!

### Крок 3 — перевірити баланс (поверне старе значення або помилку)

```bash
curl http://localhost:8080/accounts
# null або {"error": "counter unavailable"}
```

### Крок 4 — відновити counter-service

```bash
docker unpause counter
```

### Крок 5 — через кілька секунд counter вичитає чергу

```bash
curl http://localhost:8080/accounts
# {"1": 150}   # 15 транзакцій × 10
```

---

## Перевірити що різні екземпляри logging отримують повідомлення

```bash
docker logs logging1
docker logs logging2
docker logs logging3
```

У кожного буде видно `📥 [<hostname>] LOGGED: {...}` для різних транзакцій.

---

## Навантажувальне тестування

```bash
python client.py
```
