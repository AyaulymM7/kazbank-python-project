"""
Step 6, задача 3: 20 одновременных запросов (через потоки).
Сначала запусти сервер (python app.py), потом этот скрипт.
Смотрим: запросов 20, а соединений в пуле не больше 8 -> соединения переиспользуются.
"""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:5000"


def get(path):
    with urllib.request.urlopen(BASE + path) as resp:
        return resp.status


def transfer(_):
    body = json.dumps({"from_account": 6, "to_account": 3, "amount": 100}).encode()
    req = urllib.request.Request(BASE + "/transfer", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


print("Before:", json.load(urllib.request.urlopen(BASE + "/health"))["pool"])

with ThreadPoolExecutor(max_workers=20) as ex:              # 20 потоков одновременно
    codes = list(ex.map(lambda _: get("/customers"), range(20)))
print("20 x GET /customers ->", codes)

with ThreadPoolExecutor(max_workers=20) as ex:
    codes = list(ex.map(transfer, range(20)))
print("20 x POST /transfer ->", codes)

stats = json.load(urllib.request.urlopen(BASE + "/health"))["pool"]
print("After:", stats)
print(f"Requests served: {stats['requests_num']}, connections opened: {stats['connections_num']}")
