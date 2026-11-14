"""
KazBank Transaction API (Step 3-7).
Запуск: python app.py   ->  http://127.0.0.1:5000
"""
import time
from decimal import Decimal, InvalidOperation

import psycopg
from psycopg import errors as pg_errors
from psycopg import IsolationLevel
from flask import Flask, jsonify, request

from db import pool

app = Flask(__name__)


# ---------- Общая обработка "БД недоступна" (R6: OperationalError -> 503) ----------
# PoolTimeout тоже является наследником OperationalError, поэтому ловится здесь же.
@app.errorhandler(psycopg.OperationalError)
def db_unavailable(e):
    return jsonify({"error": "Database unavailable"}), 503


class BadRequest(Exception):
    """Наша ошибка для неверных входных данных (-> 400 или 404)."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(BadRequest)
def bad_request(e):
    return jsonify({"error": e.message}), e.status


def parse_amount(value):
    """Превращаем сумму из JSON в Decimal и проверяем, что она > 0."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise BadRequest("amount must be a number")
    if amount <= 0:
        raise BadRequest("amount must be positive")
    return amount


# ============================ CUSTOMERS ============================

# GET /customers            - все клиенты
# GET /customers?city=Almaty - поиск по городу
@app.route("/customers", methods=["GET"])
def list_customers():
    city = request.args.get("city")
    if city:
        sql = "SELECT customer_id, full_name, city, email FROM customers WHERE city = %s ORDER BY customer_id"
        args = (city,)          # %s -> параметр, SQL-инъекция невозможна
    else:
        sql = "SELECT customer_id, full_name, city, email FROM customers ORDER BY customer_id"
        args = ()
    with pool.connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return jsonify([{"id": r[0], "name": r[1], "city": r[2], "email": r[3]} for r in rows])


# POST /customers  body: {"full_name": "...", "city": "...", "email": "..."}
@app.route("/customers", methods=["POST"])
def create_customer():
    data = request.get_json(silent=True) or {}
    with pool.connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO customers (full_name, city, email) VALUES (%s, %s, %s) RETURNING customer_id",
                (data.get("full_name"), data.get("city", "Almaty"), data.get("email")),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"customer_id": new_id}), 201
        except pg_errors.UniqueViolation:
            conn.rollback()
            return jsonify({"error": "Email already registered"}), 409
        except pg_errors.NotNullViolation as e:
            conn.rollback()
            return jsonify({"error": f"Missing required field: {e.diag.column_name}"}), 400


# PUT /customers/<id>  body: {"full_name": "...", "city": "..."}
@app.route("/customers/<int:cid>", methods=["PUT"])
def update_customer(cid):
    data = request.get_json(silent=True) or {}
    with pool.connection() as conn:
        try:
            cur = conn.execute(
                "UPDATE customers SET full_name = %s, city = %s WHERE customer_id = %s",
                (data.get("full_name"), data.get("city"), cid),
            )
            conn.commit()
        except pg_errors.NotNullViolation as e:
            conn.rollback()
            return jsonify({"error": f"Missing required field: {e.diag.column_name}"}), 400
    if cur.rowcount == 0:                       # ни одна строка не изменилась
        return jsonify({"error": "Customer not found"}), 404
    return jsonify({"updated": cid})


# DELETE /customers/<id>
@app.route("/customers/<int:cid>", methods=["DELETE"])
def delete_customer(cid):
    with pool.connection() as conn:
        cur = conn.execute("DELETE FROM customers WHERE customer_id = %s", (cid,))
        conn.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Customer not found"}), 404
    return jsonify({"deleted": cid})


# ============================ ACCOUNTS ============================

# GET /accounts?customer_id=1
@app.route("/accounts", methods=["GET"])
def list_accounts():
    customer_id = request.args.get("customer_id", type=int)   # не число -> None
    if customer_id is None:
        raise BadRequest("customer_id query parameter (integer) is required")
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT account_id, account_number, balance FROM accounts WHERE customer_id = %s ORDER BY account_id",
            (customer_id,),
        ).fetchall()
    return jsonify([{"account_id": r[0], "account_number": r[1], "balance": float(r[2])} for r in rows])


# ============================ TRANSACTIONS ============================

# GET /transactions?account_id=1  - история операций по счёту
@app.route("/transactions", methods=["GET"])
def list_transactions():
    account_id = request.args.get("account_id", type=int)
    if account_id is None:
        raise BadRequest("account_id query parameter (integer) is required")
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT tx_id, amount, tx_type, created_at FROM transactions WHERE account_id = %s ORDER BY tx_id",
            (account_id,),
        ).fetchall()
    return jsonify([
        {"tx_id": r[0], "amount": float(r[1]), "tx_type": r[2], "created_at": r[3].isoformat()}
        for r in rows
    ])


# POST /transactions  body: {"account_id": 1, "amount": 1000, "tx_type": "debit" | "credit"}
# debit = снять деньги, credit = положить деньги. Баланс не может стать < 0.
@app.route("/transactions", methods=["POST"])
def create_transaction():
    data = request.get_json(silent=True) or {}
    amount = parse_amount(data.get("amount"))
    tx_type = data.get("tx_type")
    if tx_type not in ("debit", "credit"):
        raise BadRequest("tx_type must be 'debit' or 'credit'")

    with pool.connection() as conn:
        try:
            # FOR UPDATE - блокируем строку счёта, пока не закончим
            row = conn.execute(
                "SELECT balance FROM accounts WHERE account_id = %s FOR UPDATE",
                (data.get("account_id"),),
            ).fetchone()
            if row is None:
                raise BadRequest("Account not found", 404)

            new_balance = row[0] - amount if tx_type == "debit" else row[0] + amount
            if new_balance < 0:
                raise BadRequest("Insufficient funds")

            conn.execute("UPDATE accounts SET balance = %s WHERE account_id = %s",
                         (new_balance, data.get("account_id")))
            conn.execute("INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, %s)",
                         (data.get("account_id"), amount, tx_type))
            conn.commit()        # оба действия сохраняются вместе
        except Exception:
            conn.rollback()      # при любой ошибке - ничего не сохраняется
            raise
    return jsonify({"account_id": data.get("account_id"), "new_balance": float(new_balance)}), 201


# ============================ TRANSFER ============================

def with_retry(fn, max_retries=3):
    """Повторяем fn(), если SERIALIZABLE-транзакция упала с конфликтом (код 40001)."""
    for attempt in range(max_retries):
        try:
            return fn()
        except pg_errors.SerializationFailure:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.05 * (attempt + 1))   # небольшая пауза и пробуем снова


def do_transfer(from_acc, to_acc, amount):
    """Перевод денег. Либо оба UPDATE выполнятся, либо ни одного (атомарность)."""
    with pool.connection() as conn:
        conn.isolation_level = IsolationLevel.SERIALIZABLE   # самый строгий уровень
        try:
            # 1) Блокируем оба счёта ВСЕГДА в одном порядке (меньший id первым),
            #    чтобы не было deadlock.
            first, second = sorted([from_acc, to_acc])
            found = 0
            for acc in (first, second):
                if conn.execute("SELECT 1 FROM accounts WHERE account_id = %s FOR UPDATE", (acc,)).fetchone():
                    found += 1
            if found < 2:
                raise BadRequest("Account not found", 404)

            # 2) Проверяем, хватает ли денег
            balance = conn.execute("SELECT balance FROM accounts WHERE account_id = %s",
                                   (from_acc,)).fetchone()[0]
            if balance < amount:
                raise BadRequest("Insufficient funds")

            # 3) Главная часть: два UPDATE в одной транзакции
            conn.execute("UPDATE accounts SET balance = balance - %s WHERE account_id = %s", (amount, from_acc))
            conn.execute("UPDATE accounts SET balance = balance + %s WHERE account_id = %s", (amount, to_acc))

            # 4) SAVEPOINT: запись в историю - отдельный шаг.
            #    Если он упадёт из-за ограничения, откатываем ТОЛЬКО его,
            #    а сам перевод (шаг 3) сохраняется.
            history_saved = True
            conn.execute("SAVEPOINT log_step")
            try:
                conn.execute("INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, 'debit')",
                             (from_acc, amount))
                conn.execute("INSERT INTO transactions (account_id, amount, tx_type) VALUES (%s, %s, 'credit')",
                             (to_acc, amount))
                conn.execute("RELEASE SAVEPOINT log_step")
            except pg_errors.IntegrityError:
                conn.execute("ROLLBACK TO SAVEPOINT log_step")
                history_saved = False

            conn.commit()
            return {"from": from_acc, "to": to_acc, "amount": float(amount), "history_saved": history_saved}
        except Exception:
            conn.rollback()
            raise
        finally:
            # соединение вернётся в пул - сбрасываем уровень изоляции на стандартный,
            # чтобы другие запросы не получили SERIALIZABLE "в наследство"
            conn.isolation_level = None


# POST /transfer  body: {"from_account": 1, "to_account": 2, "amount": 5000}
@app.route("/transfer", methods=["POST"])
def transfer():
    data = request.get_json(silent=True) or {}
    from_acc = data.get("from_account")
    to_acc = data.get("to_account")
    if not isinstance(from_acc, int) or not isinstance(to_acc, int):
        raise BadRequest("from_account and to_account must be integers")
    if from_acc == to_acc:
        raise BadRequest("Cannot transfer to the same account")
    amount = parse_amount(data.get("amount"))

    try:
        result = with_retry(lambda: do_transfer(from_acc, to_acc, amount))
    except pg_errors.SerializationFailure:
        return jsonify({"error": "Too many concurrent transfers, try again"}), 409
    except pg_errors.CheckViolation:
        return jsonify({"error": "Balance cannot be negative"}), 400
    return jsonify(result), 200


# ============================ HEALTH ============================

# GET /health - проверка БД и статистика пула (R8)
@app.route("/health", methods=["GET"])
def health():
    try:
        pool.check()                       # проверяет простаивающие соединения, плохие выкидывает
        with pool.connection() as conn:    # и реально спрашиваем БД
            conn.execute("SELECT 1")
        return jsonify({"status": "ok", "pool": pool.get_stats()})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 503


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, threaded=True)  # reloader off: иначе пул создался бы дважды
