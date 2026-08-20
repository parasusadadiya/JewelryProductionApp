import sqlite3

connection = sqlite3.connect("database/production.db")

columns = connection.execute(
    "PRAGMA table_info(todos)"
).fetchall()

for column in columns:
    print(column)

connection.close()