from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://jkorm:jkorm@localhost/pos_system"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

try:
    conn = psycopg2.connect(
        dbname="pos_system",
        user="jkorm",
        password="jkorm",
        host="localhost"
    )
except Exception as e:
    print(f"Error connecting to the database: {e}")
    raise e