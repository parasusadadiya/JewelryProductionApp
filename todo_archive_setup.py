import sqlite3

DATABASE = "database/production.db"

connection = sqlite3.connect(DATABASE)

columns = [
    row[1]
    for row in connection.execute(
        "PRAGMA table_info(todos)"
    ).fetchall()
]

if "archived" not in columns:

    connection.execute(
        """
        ALTER TABLE todos
        ADD COLUMN archived INTEGER NOT NULL DEFAULT 0
        """
    )

    print("archived column added successfully.")

else:

    print("archived column already exists.")


if "archived_at" not in columns:

    connection.execute(
        """
        ALTER TABLE todos
        ADD COLUMN archived_at TEXT
        """
    )

    print("archived_at column added successfully.")

else:

    print("archived_at column already exists.")


connection.commit()
connection.close()

print("To-Do archive setup complete.")