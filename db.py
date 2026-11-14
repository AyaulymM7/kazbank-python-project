"""
Step 6 / R3: пул соединений.
Пул создаётся ОДИН раз при импорте модуля (то есть при старте приложения),
а не в каждом запросе. Запрос "берёт" соединение и потом возвращает его.
"""
import os
import atexit
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

pool = ConnectionPool(
    conninfo=os.environ["DATABASE_URL"],
    min_size=2,     # 2 соединения всегда открыты
    max_size=8,     # максимум 8 одновременно (требование мини-проекта)
    timeout=5.0,    # если свободного соединения нет 5 секунд -> PoolTimeout (-> 503)
    open=True,
)

# при остановке сервера (Ctrl+C) аккуратно закрываем пул
atexit.register(pool.close)
