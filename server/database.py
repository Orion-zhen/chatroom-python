import sqlite3

database = sqlite3.connect('server/database.db')
cursor = database.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL
)''')


def get_user(username):
    row = cursor.execute(f"SELECT * FROM users WHERE username='{username}'").fetchall()
    if row:
        return None
    else:
        return row
    

def add_user(username, password):
    cursor.execute(f"INSERT INTO users VALUES ('{username}', '{password}')")
    database.commit()