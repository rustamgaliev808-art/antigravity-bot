"""Role-checked payment and kitchen transitions, independent of Telegram UI."""
from contextlib import closing

PAYMENT_LABELS = {"legacy_unknown": "Нужна ручная проверка старого заказа", "pending": "Ожидает оплаты", "review": "Ожидает проверки владельцем", "confirmed": "Оплата подтверждена"}


class ActionError(ValueError):
    pass


def migrate(conn):
    columns = {r[1] for r in conn.execute("PRAGMA table_info(orders)")}
    for name, definition in {"payment_status": "TEXT NOT NULL DEFAULT 'legacy_unknown'", "payment_confirmed_by": "INTEGER", "payment_confirmed_at": "TEXT"}.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {definition}")
    conn.execute("CREATE TABLE IF NOT EXISTS drafts(user_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")


def change_payment(connect, order_id, actor, action, owner, now):
    with closing(connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            raise ActionError("Заказ не найден.")
        if action == "confirm" and (not owner or actor != owner):
            raise ActionError("Подтверждать оплату может только владелец.")
        if action == "report" and actor != row["user_id"]:
            raise ActionError("Заказ не найден.")
        if action not in {"confirm", "report"}:
            raise ActionError("Недоступное действие.")
        if row["payment_status"] == "confirmed":
            return False
        if row["status"] == "cancelled":
            raise ActionError("Заказ отменён. Владелец должен отдельно проверить возможный возврат.")
        if action == "confirm":
            conn.execute("UPDATE orders SET payment_status='confirmed',payment_confirmed_by=?,payment_confirmed_at=? WHERE order_id=?", (actor, now, order_id))
        else:
            if row["payment_status"] == "review":
                return False
            conn.execute("UPDATE orders SET payment_status='review' WHERE order_id=?", (order_id,))
        return True


def change_status(connect, order_id, status, actor, owner, kitchen):
    if actor is None or actor not in ({owner} | set(kitchen)) or actor <= 0:
        raise ActionError("Доступ закрыт.")
    if status == "cancelled" and actor != owner:
        raise ActionError("Отменить заказ может только владелец.")
    with closing(connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            raise ActionError("Заказ не найден.")
        if row["status"] == status:
            return False
        if row["status"] in {"cancelled", "delivered"}:
            raise ActionError("Заказ уже завершён.")
        if status != "cancelled":
            if row["payment_status"] != "confirmed":
                raise ActionError("Сначала владелец должен подтвердить поступление оплаты.")
            expected = {"new": "cooking", "paid": "cooking", "cooking": "ready", "ready": "delivered"}.get(row["status"])
            if status != expected:
                raise ActionError("Выдача доступна только из статуса «Готов». Соблюдайте порядок приготовления.")
        if status == "cancelled" and not row["rewards_applied"]:
            conn.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE user_id=?", (row["points_used"], row["user_id"]))
        if status == "delivered" and not row["rewards_applied"]:
            conn.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE user_id=?", (row["points_earned"], row["user_id"]))
            conn.execute("UPDATE orders SET rewards_applied=1 WHERE order_id=?", (order_id,))
        conn.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
        return True
