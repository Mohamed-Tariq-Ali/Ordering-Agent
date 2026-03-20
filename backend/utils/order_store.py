from backend.utils.database import get_connection, init_db
from backend.models.schemas import Order, OrderItem
import json

init_db()


def save_order(order: Order, username: str = None) -> Order:
    conn = get_connection()
    items_json = json.dumps([item.model_dump() for item in order.items])
    conn.execute("""
        INSERT OR REPLACE INTO orders
        (order_id, username, customer_name, items, total_amount, status, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order.order_id,
        username,
        order.customer_name,
        items_json,
        order.total_amount,
        order.status,
        order.created_at,
        order.notes
    ))
    conn.commit()
    conn.close()
    return order


def get_order(order_id: str, username: str = None) -> Order | None:
    conn = get_connection()
    if username:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ? AND username = ?",
            (order_id, username)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_order(row)


def get_all_orders(username: str = None) -> list[Order]:
    conn = get_connection()
    if username:
        rows = conn.execute(
            "SELECT * FROM orders WHERE username = ? ORDER BY created_at DESC",
            (username,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [_row_to_order(row) for row in rows]


def update_order_status(order_id: str, status: str, username: str = None) -> Order | None:
    conn = get_connection()
    if username:
        conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ? AND username = ?",
            (status, order_id, username)
        )
    else:
        conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (status, order_id)
        )
    conn.commit()
    conn.close()
    return get_order(order_id, username)


def _row_to_order(row) -> Order:
    items_data = json.loads(row["items"])
    items = [OrderItem(**item) for item in items_data]
    return Order(
        order_id=row["order_id"],
        customer_name=row["customer_name"],
        items=items,
        total_amount=row["total_amount"],
        status=row["status"],
        created_at=row["created_at"],
        notes=row["notes"]
    )