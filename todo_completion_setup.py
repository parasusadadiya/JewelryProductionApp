import sqlite3

DB_PATH = "database/production.db"

connection = sqlite3.connect(DB_PATH)

columns = connection.execute(
    "PRAGMA table_info(todos)"
).fetchall()

column_names = [column[1] for column in columns]

if "completed_at" not in column_names:

    connection.execute(
        """
        ALTER TABLE todos
        ADD COLUMN completed_at TEXT
        """
    )

    connection.commit()

    print("completed_at column added successfully.")

else:

    print("completed_at column already exists.")

connection.close()