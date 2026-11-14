"""
Step 2 / R1: создаём схему KazBank и заполняем тестовыми данными.
Скрипт можно запускать много раз: он сначала удаляет старые таблицы.
"""
import os
import psycopg
from psycopg import errors as pg_errors
from dotenv import load_dotenv

load_dotenv()
conn_str = os.environ["DATABASE_URL"]

DDL = """
DROP TABLE IF EXISTS transactions, accounts, customers CASCADE;

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    city        TEXT DEFAULT 'Almaty',
    email       TEXT UNIQUE                 -- одинаковый email нельзя -> 409
);

CREATE TABLE accounts (
    account_id     SERIAL PRIMARY KEY,
    account_number TEXT NOT NULL UNIQUE,    -- номер счёта уникален (Step 2, задача 3)
    customer_id    INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    balance        NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (balance >= 0)  -- баланс не уходит в минус
);

CREATE TABLE transactions (
    tx_id      SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    amount     NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    tx_type    TEXT NOT NULL CHECK (tx_type IN ('debit', 'credit')),  -- debit = списание, credit = пополнение
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
"""

# 10 клиентов: (имя, город, email)
SEED_CUSTOMERS = [
    ("Arman Bekov",      "Almaty",    "arman@mail.kz"),
    ("Zarina Seiit",     "Astana",    "zarina@mail.kz"),
    ("Daniyar Nurlan",   "Shymkent",  "daniyar@mail.kz"),
    ("Aigerim Sadykova", "Almaty",    "aigerim@mail.kz"),
    ("Nursultan Ali",    "Karaganda", "nursultan@mail.kz"),
    ("Madina Omarova",   "Almaty",    "madina@mail.kz"),
    ("Yerlan Tokayev",   "Astana",    "yerlan@mail.kz"),
    ("Dana Kassymova",   "Aktobe",    "dana@mail.kz"),
    ("Timur Zhanov",     "Almaty",    "timur@mail.kz"),
    ("Aruzhan Bek",      "Shymkent",  "aruzhan@mail.kz"),
]

# 15 счетов: (номер счёта, id клиента, баланс)
SEED_ACCOUNTS = [
    ("KZ0001", 1, 500000), ("KZ0002", 1, 120000),
    ("KZ0003", 2, 300000), ("KZ0004", 3, 50000),
    ("KZ0005", 3, 75000),  ("KZ0006", 4, 1000000),
    ("KZ0007", 5, 20000),  ("KZ0008", 6, 450000),
    ("KZ0009", 6, 10000),  ("KZ0010", 7, 0),
    ("KZ0011", 8, 250000), ("KZ0012", 9, 90000),
    ("KZ0013", 9, 60000),  ("KZ0014", 10, 330000),
    ("KZ0015", 10, 15000),
]

with psycopg.connect(conn_str) as conn:
    conn.execute(DDL)
    # executemany - одна команда на много строк, быстрее чем execute в цикле
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO customers (full_name, city, email) VALUES (%s, %s, %s)",
            SEED_CUSTOMERS,
        )
        cur.executemany(
            "INSERT INTO accounts (account_number, customer_id, balance) VALUES (%s, %s, %s)",
            SEED_ACCOUNTS,
        )
    conn.commit()
    print("Schema created: 10 customers, 15 accounts")

    # Проверка UNIQUE: пробуем вставить уже существующий номер счёта
    try:
        conn.execute(
            "INSERT INTO accounts (account_number, customer_id, balance) VALUES (%s, %s, %s)",
            ("KZ0001", 2, 100),
        )
        conn.commit()
    except pg_errors.UniqueViolation as e:
        conn.rollback()  # после ошибки транзакцию нужно откатить
        print("UNIQUE works, duplicate rejected:", e.diag.message_primary)
