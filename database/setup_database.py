import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).parent / "company.db"


def create_database():
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    # -------------------------
    # Customers
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)

    # -------------------------
    # Orders
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            delivery_date TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)

    # -------------------------
    # Support Tickets
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_id TEXT,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            response TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    """)

    # -------------------------
    # Refunds
    # -------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    """)

    # -------------------------
    # Insert customers
    # -------------------------
    customers = [
        ("C001", "Rahul Sharma", "rahul@example.com"),
        ("C002", "Priya Patel", "priya@example.com"),
        ("C003", "Arjun Kumar", "arjun@example.com"),
        ("C004", "Sneha Reddy", "sneha@example.com"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO customers
        VALUES (?, ?, ?)
    """, customers)

    # -------------------------
    # Insert orders
    # -------------------------
    orders = [
        ("O1001", "C001", 2499.00, "Delivered", "2026-10-01"),
        ("O1002", "C002", 4500.00, "Delayed", None),
        ("O1003", "C003", 1299.00, "Shipped", None),
        ("O1004", "C004", 3200.00, "Delivered", "2026-10-03"),
        ("O1005", "C001", 1800.00, "Cancelled", None),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO orders
        VALUES (?, ?, ?, ?, ?)
    """, orders)

    # -------------------------
    # Insert support tickets
    # -------------------------
    tickets = [
        (
            "T1001",
            "C001",
            "O1001",
            "Delivery complaint",
            "Customer says the order was delayed and wants an update.",
            "Open",
            "Medium",
            None
        ),
        (
            "T1002",
            "C002",
            "O1002",
            "Order delayed",
            "Customer has not received the order and wants to know the status.",
            "Open",
            "High",
            None
        ),
        (
            "T1003",
            "C003",
            "O1003",
            "Delivery status",
            "Customer wants to know when the order will arrive.",
            "Open",
            "Low",
            None
        ),
        (
            "T1004",
            "C004",
            "O1004",
            "Refund request",
            "Customer is requesting a refund for the delivered order.",
            "Open",
            "High",
            None
        ),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO tickets
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, tickets)

    # -------------------------
    # Insert refunds
    # -------------------------
    refunds = [
        (
            "R001",
            "T1004",
            "O1004",
            3200.00,
            "Pending Approval"
        )
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO refunds
        VALUES (?, ?, ?, ?, ?)
    """, refunds)

    connection.commit()
    connection.close()

    print(f"Database created successfully: {DATABASE_PATH}")


if __name__ == "__main__":
    create_database()