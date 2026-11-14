"""
Step 1: проверка подключения.
  1) печатаем версию PostgreSQL
  2) строку подключения берём из .env (python-dotenv)
  3) проверяем, что autocommit по умолчанию = False
"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()                              # читает файл .env в переменные окружения
conn_str = os.environ["DATABASE_URL"]      # пароль НЕ хранится в коде

with psycopg.connect(conn_str) as conn:
    row = conn.execute("SELECT version()").fetchone()
    print("PostgreSQL version:", row[0])
    print("autocommit =", conn.autocommit)  # False -> изменения надо подтверждать commit()
