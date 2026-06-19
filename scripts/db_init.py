import duckdb, os
from dotenv import load_dotenv
load_dotenv()

con = duckdb.connect(f"md:?motherduck_token={os.getenv('MOTHERDUCK_TOKEN')}")
con.execute("CREATE DATABASE IF NOT EXISTS agri_dwh")
con.execute("USE agri_dwh")
con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
con.execute("CREATE SCHEMA IF NOT EXISTS silver")
con.execute("CREATE SCHEMA IF NOT EXISTS gold")

con.execute("""
CREATE TABLE IF NOT EXISTS gold.forecast_lstm (
    forecast_date DATE,
    commodity VARCHAR,
    predicted_price DOUBLE,
    ci_lower DOUBLE,
    ci_upper DOUBLE
)
""")

print("Schemas created:", con.execute("SELECT schema_name FROM information_schema.schemata WHERE catalog_name = 'agri_dwh'").fetchall())
con.close()