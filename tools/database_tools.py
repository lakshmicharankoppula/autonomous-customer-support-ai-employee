import sqlite3
from pathlib import Path


DATABASE_PATH = (
    Path(__file__).resolve().parent.parent
    / "database"
    / "company.db"
)


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def search_customer(name: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT customer_id, name, email
        FROM customers
        WHERE name LIKE ?
        """,
        (f"%{name}%",)
    )

    results = cursor.fetchall()
    connection.close()

    return results


def get_customer(customer_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT customer_id, name, email
        FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,)
    )

    result = cursor.fetchone()
    connection.close()

    return result


def get_order(order_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            order_id,
            customer_id,
            amount,
            status,
            delivery_date
        FROM orders
        WHERE order_id = ?
        """,
        (order_id,)
    )

    result = cursor.fetchone()
    connection.close()

    return result


def search_tickets(status=None):
    connection = get_connection()
    cursor = connection.cursor()

    if status:
        cursor.execute(
            """
            SELECT
                ticket_id,
                customer_id,
                order_id,
                subject,
                description,
                status,
                priority,
                response
            FROM tickets
            WHERE status = ?
            """,
            (status,)
        )
    else:
        cursor.execute(
            """
            SELECT
                ticket_id,
                customer_id,
                order_id,
                subject,
                description,
                status,
                priority,
                response
            FROM tickets
            """
        )

    results = cursor.fetchall()
    connection.close()

    return results


def get_ticket(ticket_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            ticket_id,
            customer_id,
            order_id,
            subject,
            description,
            status,
            priority,
            response
        FROM tickets
        WHERE ticket_id = ?
        """,
        (ticket_id,)
    )

    result = cursor.fetchone()
    connection.close()

    return result


def update_ticket(ticket_id: str, response: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE tickets
        SET response = ?
        WHERE ticket_id = ?
        """,
        (response, ticket_id)
    )

    connection.commit()

    success = cursor.rowcount > 0

    connection.close()

    return success


def resolve_ticket(ticket_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE tickets
        SET status = 'Resolved'
        WHERE ticket_id = ?
        """,
        (ticket_id,)
    )

    connection.commit()

    success = cursor.rowcount > 0

    connection.close()

    return success


def get_refund(ticket_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            refund_id,
            ticket_id,
            order_id,
            amount,
            status
        FROM refunds
        WHERE ticket_id = ?
        """,
        (ticket_id,)
    )

    result = cursor.fetchone()
    connection.close()

    return result