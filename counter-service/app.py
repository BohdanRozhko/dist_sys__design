from fastapi import FastAPI
import psycopg2

app = FastAPI()

conn = psycopg2.connect(
    host="postgres",
    database="bank",
    user="user",
    password="password"
)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    user_id INT PRIMARY KEY,
    balance INT
)
""")
conn.commit()


@app.post("/update")
def update_balance(data: dict):
    user_id = data["user_id"]
    amount = data["amount"]

    cur.execute("SELECT balance FROM accounts WHERE user_id=%s", (user_id,))
    row = cur.fetchone()

    if row:
        balance = row[0] + amount
        cur.execute("UPDATE accounts SET balance=%s WHERE user_id=%s", (balance, user_id))
    else:
        balance = amount
        cur.execute("INSERT INTO accounts VALUES (%s, %s)", (user_id, balance))

    conn.commit()

    return {"balance": balance}


@app.get("/accounts")
def get_accounts():
    cur.execute("SELECT user_id, balance FROM accounts")
    rows = cur.fetchall()

    return {str(r[0]): r[1] for r in rows}
