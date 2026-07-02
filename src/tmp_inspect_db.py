from config import get_settings
import sqlite3
s = get_settings()
print('DB path:', s.PATH_TO_DB)
conn = sqlite3.connect(s.PATH_TO_DB)
cur = conn.cursor()
print('tables:', cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
try:
    print('user_groups:', cur.execute('SELECT id, name FROM user_groups').fetchall())
except Exception as e:
    print('user_groups error', e)
try:
    print('users:', cur.execute('SELECT id, email FROM users').fetchall())
except Exception as e:
    print('users error', e)
conn.close()
