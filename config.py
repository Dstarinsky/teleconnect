# config.py
import os
from dotenv import load_dotenv
from mysql.connector import pooling

def load_environment(env_file: str = ".env"):
    load_dotenv(dotenv_path=env_file)

def create_db_pool():
    return pooling.MySQLConnectionPool(
        pool_name="bot_pool",
        pool_size=5,
        pool_reset_session=True,
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME")
    )