import duckdb, os
from dotenv import load_dotenv
load_dotenv()

con = duckdb.connect(f"md:agri_dwh?motherduck_token={os.getenv('MOTHERDUCK_TOKEN')}")
con.execute("CREATE DATABASE IF NOT EXISTS agri_dwh")
con.execute("USE agri_dwh")
con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
con.execute("CREATE SCHEMA IF NOT EXISTS silver")  
con.execute("CREATE SCHEMA IF NOT EXISTS gold")
print("Schemas created:", con.execute("SHOW SCHEMAS").fetchall())
con.close()