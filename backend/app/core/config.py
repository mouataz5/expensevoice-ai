import os
from dotenv import load_dotenv

load_dotenv()  # loads backend/.env

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/expensevoice",
)
