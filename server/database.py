import sqlite3

database = sqlite3.connect('server/database.db')
cursor = database.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL
)''')
cursor.close()
database.close()


def get_user(username):
    database = sqlite3.connect('server/database.db')
    cursor = database.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )''')
    # print("执行数据库搜索")
    row = cursor.execute(f"SELECT * FROM users WHERE username='{username}'").fetchall()
    print(f"搜索结果: {row}")
    if row == []:
        cursor.close()
        database.close()
        return None
    else:
        cursor.close()
        database.close()
        return row[0]
    
    
    

def add_user(username, password):
    database = sqlite3.connect('server/database.db')
    cursor = database.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )''')

    cursor.execute(f"INSERT INTO users VALUES ('{username}', '{password}')")
    database.commit()
    
    cursor.close()
    database.close()