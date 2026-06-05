import os

import duckdb
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("MOTHERDUCK_TOKEN")
database = os.getenv("MOTHERDUCK_DB", "agri_dwh")

if not token:
    raise SystemExit("MOTHERDUCK_TOKEN is missing. Add it to .env before running db_init.py")

con = duckdb.connect(f"md:?motherduck_token={token}")
con.execute(f'CREATE DATABASE IF NOT EXISTS "{database}"')
con.execute(f'USE "{database}"')
con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
con.execute("CREATE SCHEMA IF NOT EXISTS silver")
con.execute("CREATE SCHEMA IF NOT EXISTS gold")
print("Database initialized:", database)
print("Schemas created:", con.execute("SHOW SCHEMAS").fetchall())
con.close()
