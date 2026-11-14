#!/bin/bash
# Все проверки через curl (Step 3.4, Step 5.4). Сервер должен быть запущен: python app.py
# Windows: запускай в Git Bash, или повтори те же запросы в Postman.
B=http://127.0.0.1:5000
c(){ echo; echo ">>> $*"; curl -s -w "\n[HTTP %{http_code}]\n" "$@"; }
J='Content-Type: application/json'

echo "===== CUSTOMERS ====="
c "$B/customers"
c "$B/customers?city=Almaty"
c -X POST $B/customers -H "$J" -d '{"full_name":"Test User","city":"Astana","email":"test@mail.kz"}'   # 201
c -X POST $B/customers -H "$J" -d '{"full_name":"Dup","email":"test@mail.kz"}'                        # 409 duplicate email
c -X POST $B/customers -H "$J" -d '{"city":"Astana"}'                                                 # 400 no full_name
c -X PUT  $B/customers/1 -H "$J" -d '{"full_name":"Arman Bekov","city":"Almaty"}'                     # 200
c -X DELETE $B/customers/999                                                                         # 404

echo "===== SQL INJECTION (должно вернуть [] а не всех клиентов) ====="
c "$B/customers?city=Almaty'%20OR%20'1'='1"
c "$B/customers?city=x';%20DROP%20TABLE%20customers;--"
c "$B/customers"   # таблица на месте

echo "===== ACCOUNTS / TRANSACTIONS ====="
c "$B/accounts?customer_id=1"
c -X POST $B/transactions -H "$J" -d '{"account_id":1,"amount":1000,"tx_type":"debit"}'     # 201
c -X POST $B/transactions -H "$J" -d '{"account_id":10,"amount":1000,"tx_type":"debit"}'    # 400 insufficient funds
c -X POST $B/transactions -H "$J" -d '{"account_id":10,"amount":500,"tx_type":"credit"}'    # 201
c "$B/transactions?account_id=1"

echo "===== TRANSFER ====="
c -X POST $B/transfer -H "$J" -d '{"from_account":1,"to_account":2,"amount":5000}'    # 200
c -X POST $B/transfer -H "$J" -d '{"from_account":7,"to_account":2,"amount":999999}'  # 400 insufficient funds
c -X POST $B/transfer -H "$J" -d '{"from_account":1,"to_account":999,"amount":10}'    # 404
c -X POST $B/transfer -H "$J" -d '{"from_account":1,"to_account":1,"amount":10}'      # 400 same account
c "$B/accounts?customer_id=1"

echo "===== HEALTH ====="
c $B/health
# Для 503: останови PostgreSQL и повтори  curl $B/customers
