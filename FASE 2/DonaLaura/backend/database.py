
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


# Ubicación de la carpeta backend
BASE_DIR = Path(__file__).resolve().parent

# Cargar el archivo .env de esa carpeta
load_dotenv(BASE_DIR / ".env", override=True)


def conectar_bd():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )