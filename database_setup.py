import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)

DATABASE = DATABASE_DIR / "production.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database():
    connection = get_connection()

    cursor = connection.cursor()

    # Customers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Orders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            order_type TEXT NOT NULL,
            product_number TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            order_date TEXT,
            due_date TEXT,
            photo_path TEXT,
            notes TEXT,
            current_stage TEXT NOT NULL DEFAULT 'Customer Order',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (customer_id)
                REFERENCES customers(id)
        )
    """)

    # Production stages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            stage_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            started_at TEXT,
            completed_at TEXT,
            notes TEXT,

            FOREIGN KEY (order_id)
                REFERENCES orders(id)
        )
    """)

    connection.commit()
    connection.close()

    print(f"Database created successfully:")
    print(DATABASE)


if __name__ == "__main__":
    setup_database()
# Add production tracking fields if they do not already exist

import sqlite3

DATABASE = "database/production.db"

connection = sqlite3.connect(DATABASE)

columns = [
    ("started_at", "TEXT"),
    ("completed_at", "TEXT"),
    ("notes", "TEXT")
]

for column_name, column_type in columns:
    try:
        connection.execute(
            f"ALTER TABLE production_stages ADD COLUMN {column_name} {column_type}"
        )
    except sqlite3.OperationalError:
        pass

connection.commit()
connection.close()

print("Production stage tracking fields are ready.")