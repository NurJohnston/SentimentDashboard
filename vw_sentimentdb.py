import sqlite3

def view_database():
    conn = sqlite3.connect('sentiment.db')
    c = conn.cursor()
    
    print("=" * 50)
    print("DATABASE CONTENTS")
    print("=" * 50)
    
    # Show all tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print(f"\nTables: {[t[0] for t in tables]}")
    
    for table in tables:
        table_name = table[0]
        print(f"\n📋 Table: {table_name}")
        print("-" * 30)
        
        # Get column names
        c.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in c.fetchall()]
        print(f"Columns: {', '.join(columns)}")
        
        # Get data
        c.execute(f"SELECT * FROM {table_name}")
        rows = c.fetchall()
        
        if rows:
            for row in rows:
                print(row)
        else:
            print("(no data)")
    
    conn.close()

if __name__ == "__main__":
    view_database()