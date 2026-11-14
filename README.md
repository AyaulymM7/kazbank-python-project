# KazBank Transaction API — Python + PostgreSQL

CSCI2204 DBMS, KBTU Fall 2026. Flask REST API over PostgreSQL using psycopg3 and a connection pool.

## Project files

| File | What it does | Step |
|---|---|---|
| `step1_check.py` | Connects, prints PG version, shows `autocommit = False` | 1 |
| `setup_db.py` | Creates schema (customers, accounts, transactions), seeds 10 customers / 15 accounts with `executemany`, tests UNIQUE | 2, R1 |
| `db.py` | Creates one shared `ConnectionPool` (min 2, max 8) at startup | 6, R3 |
| `app.py` | All endpoints, transactions, error handling, retry | 3–7 |
| `deadlock_demo.sql` | Step-by-step deadlock in two psql sessions | 4.4 |
| `load_test.py` | 20 concurrent requests with threads, prints pool stats | 6.3 |
| `test_requests.sh` | curl tests for every endpoint, error code and SQL injection | 3.4, 5.4 |

## How to run

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# create the database once
psql -U postgres -c "CREATE DATABASE kazbank;"

# put your password into .env
cp .env.example .env              # Windows: copy .env.example .env

python step1_check.py             # Step 1
python setup_db.py                # Step 2: schema + seed (safe to re-run, it resets data)
python app.py                     # server on http://127.0.0.1:5000

# in a second terminal
./test_requests.sh                # all curl tests
python load_test.py               # pool load test
```

## Endpoints

| Method | URL | Body | Codes |
|---|---|---|---|
| GET | `/customers` , `/customers?city=Almaty` | – | 200 |
| POST | `/customers` | `{"full_name","city","email"}` | 201, 400, 409 |
| PUT | `/customers/<id>` | `{"full_name","city"}` | 200, 400, 404 |
| DELETE | `/customers/<id>` | – | 200, 404 |
| GET | `/accounts?customer_id=1` | – | 200, 400 |
| POST | `/transactions` | `{"account_id","amount","tx_type":"debit"/"credit"}` | 201, 400, 404 |
| GET | `/transactions?account_id=1` | – | 200, 400 |
| POST | `/transfer` | `{"from_account","to_account","amount"}` | 200, 400, 404, 409 |
| GET | `/health` | – | 200, 503 |

Any endpoint returns **503** if the database is unreachable.

## Sample curl

```bash
curl "http://127.0.0.1:5000/customers?city=Almaty"
curl -X POST http://127.0.0.1:5000/customers -H "Content-Type: application/json" \
     -d '{"full_name":"Test User","city":"Astana","email":"test@mail.kz"}'
curl "http://127.0.0.1:5000/accounts?customer_id=1"
curl -X POST http://127.0.0.1:5000/transfer -H "Content-Type: application/json" \
     -d '{"from_account":1,"to_account":2,"amount":5000}'
curl "http://127.0.0.1:5000/transactions?account_id=1"
curl http://127.0.0.1:5000/health

# SQL injection attempt -> returns [] (input is treated as plain text)
curl "http://127.0.0.1:5000/customers?city=Almaty'%20OR%20'1'='1"
```

## Design notes

- **Pool** is created once in `db.py`; every request uses `with pool.connection() as conn:` and the connection goes back to the pool automatically.
- **Transfer** runs at `SERIALIZABLE`, locks both accounts with `SELECT ... FOR UPDATE` in ascending id order (no deadlocks), does both `UPDATE`s in one transaction, and is retried up to 3 times on `SerializationFailure` (40001).
- **SAVEPOINT** in `/transfer`: writing history rows is a separate step; if it violates a constraint only that step is rolled back, the money transfer itself is kept.
- **Errors**: `UniqueViolation → 409`, `NotNullViolation → 400`, `OperationalError` / `PoolTimeout → 503`.
- **No SQL injection**: every query uses `%s` parameters, no f-strings in SQL.
