import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    # Create sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT, 
                  login_time TIMESTAMP,
                  last_activity TIMESTAMP)''')
    
    # Create user filters table
    c.execute('''CREATE TABLE IF NOT EXISTS user_filters
                 (user_id INTEGER PRIMARY KEY,
                  start_date TEXT,
                  end_date TEXT,
                  domain INTEGER,
                  placement INTEGER,
                  group_by TEXT DEFAULT 'date')''')
    
    conn.commit()
    conn.close()

def get_user_session(user_id):
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def create_session(user_id, username):
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)", 
              (user_id, username, now, now))
    conn.commit()
    conn.close()

def delete_session(user_id):
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def update_user_filters(user_id, **filters):
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    
    # Get existing filters
    c.execute("SELECT * FROM user_filters WHERE user_id=?", (user_id,))
    existing = c.fetchone()
    
    if existing:
        # Update existing
        current_filters = {
            'start_date': existing[1],
            'end_date': existing[2],
            'domain': existing[3],
            'placement': existing[4],
            'group_by': existing[5]
        }
        current_filters.update(filters)
        
        c.execute('''UPDATE user_filters SET 
                    start_date=?, end_date=?, domain=?, placement=?, group_by=?
                    WHERE user_id=?''',
                 (current_filters['start_date'], current_filters['end_date'],
                  current_filters['domain'], current_filters['placement'],
                  current_filters['group_by'], user_id))
    else:
        # Create new
        default_filters = {
            'start_date': None,
            'end_date': None,
            'domain': None,
            'placement': None,
            'group_by': 'date'
        }
        default_filters.update(filters)
        
        c.execute('''INSERT INTO user_filters VALUES 
                    (?, ?, ?, ?, ?, ?)''',
                 (user_id, default_filters['start_date'], 
                  default_filters['end_date'], default_filters['domain'],
                  default_filters['placement'], default_filters['group_by']))
    
    conn.commit()
    conn.close()

def get_user_filters(user_id):
    conn = sqlite3.connect('sessions.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user_filters WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'start_date': result[1],
            'end_date': result[2],
            'domain': result[3],
            'placement': result[4],
            'group_by': result[5]
        }
    return None

# Initialize database on import
init_db()