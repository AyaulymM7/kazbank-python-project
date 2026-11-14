-- Step 4, задача 4: симуляция deadlock в psql.
-- Открой ДВА окна терминала, в каждом:  psql -U postgres -d kazbank
-- Выполняй команды строго по шагам, переключаясь между окнами.

-- ===== Шаг 1. Окно A =====
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 1;   -- A заблокировал счёт 1

-- ===== Шаг 2. Окно B =====
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 2;   -- B заблокировал счёт 2

-- ===== Шаг 3. Окно A =====
UPDATE accounts SET balance = balance + 100 WHERE account_id = 2;   -- A ждёт счёт 2 (висит)

-- ===== Шаг 4. Окно B =====
UPDATE accounts SET balance = balance + 100 WHERE account_id = 1;   -- B ждёт счёт 1 -> DEADLOCK

-- Примерно через 1 секунду PostgreSQL убьёт одну из транзакций:
--   ERROR:  deadlock detected
--   DETAIL:  Process 3212 waits for ShareLock on transaction 782; blocked by process 3213.
--            Process 3213 waits for ShareLock on transaction 781; blocked by process 3212.
--   HINT:  See server log for query details.
-- Код ошибки: 40P01. Вторая транзакция продолжит работу.

-- ===== Шаг 5. В обоих окнах =====
ROLLBACK;

-- Как защищаемся в коде (app.py, do_transfer):
-- оба счёта блокируются через SELECT ... FOR UPDATE ВСЕГДА в порядке возрастания id
-- (first, second = sorted([from_acc, to_acc])). Тогда обе транзакции сначала
-- ждут один и тот же счёт, и "круга ожидания" не возникает.
