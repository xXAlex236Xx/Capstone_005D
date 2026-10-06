

import psycopg



from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from collections import Counter

from datetime import date

from fastapi import File, UploadFile

from importador import leer_planilla



from database import conectar_bd





# =====================================================

# CONFIGURACIÓN DE FASTAPI

# =====================================================



app = FastAPI(

    title="Sistema de Gestion Dona Laura",

    description="API de gestion administrativa agricola",

    version="0.1.0"

)



# Permitir la conexión desde nuestro frontend React

app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://localhost:5173",

        "http://127.0.0.1:5173"

    ],

    allow_credentials=False,

    allow_methods=["GET", "POST", "PUT", "PATCH"

],

    allow_headers=["*"],

)





# =====================================================

# MODELOS DE TRABAJADORES

# =====================================================



class TrabajadorCrear(BaseModel):

    nombre: str = Field(min_length=1, max_length=100)

    apellido: str = Field(min_length=1, max_length=100)

    rut: str | None = Field(default=None, max_length=12)





