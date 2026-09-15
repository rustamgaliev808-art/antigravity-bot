"""Atomic persistence. Callbacks read the catalog while the write lock is held."""
import secrets
from contextlib import closing
from order_rules import fail


def existing_order(connect, token, digest, user_id):
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM orders WHERE request_token=?", (token,)).fetchone()
        if row and (row["user_id"] != user_id or row["request_hash"] != digest):
            fail("conflict")
        return dict(row) if row else None


def save(connect, user_id, token, digest, calculate, expected_total, requested_points, date, pickup, comment, now, clear_cart=False):
    with closing(connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM orders WHERE request_token=?", (token,)).fetchone()
        if row:
            if row["user_id"] != user_id or row["request_hash"] != digest:
                fail("conflict")
            return row["order_id"], row["points_used"], row["points_earned"], row["qr_token"], False
        base, discount, components, description = calculate()
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            fail("stale")
        points = max(0, min(requested_points, int(row["balance"] or 0), int(base * .3)))
        total = base - points
        if total != expected_total or points != requested_points:
            fail("stale")
        earned, qr = int(total * .05), secrets.token_urlsafe(18)
        cur = conn.execute("INSERT INTO orders(user_id,items,total,status,pickup_time,pickup_date,created_at,discount_amount,points_used,points_earned,rewards_applied,qr_token,request_token,comment,request_hash,payment_status) VALUES (?,?,?,'new',?,?,?,?,?,?,0,?,?,?,?,'pending')", (user_id, description, total, pickup, date, now, discount, points, earned, qr, token, comment, digest))
        order_id = cur.lastrowid
        for kind, name, qty, price in components:
            conn.execute("INSERT INTO order_items(order_id,item_type,item_name,quantity,unit_price) VALUES (?,?,?,?,?)", (order_id, kind, name, qty, price))
            conn.execute("INSERT INTO order_components(order_id,component_type,component_name) VALUES (?,?,?)", (order_id, kind, name))
        conn.execute("UPDATE users SET balance=COALESCE(balance,0)-?,orders_count=orders_count+1 WHERE user_id=?", (points, user_id))
        if clear_cart:
            conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM drafts WHERE user_id=?", (user_id,))
        return order_id, points, earned, qr, True
