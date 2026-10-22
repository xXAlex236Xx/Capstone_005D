# Agricolix · Solución de Gestión Administrativa para Doña Laura SpA

Proyecto de título (Capstone APT) de Ingeniería en Informática, sede Viña del Mar.

Doña Laura SpA es una empresa agrícola de Panquehue que presta servicios de cosecha con unos 25 trabajadores. Hasta ahora llevaba los registros de producción en planillas Excel, lo que hacía difícil comparar jornadas, calcular pagos o ver cómo iba cada trabajador. Este sistema junta esa información en una sola aplicación web y le suma un módulo de análisis con inteligencia artificial que apoya al encargado, sin tomar decisiones por él.

Dentro del código y de la interfaz el sistema se llama simplemente "Doña Laura".

## Qué hace hoy

- Registro de trabajadores, sectores, labores, jornadas y producción.
- Importación de planillas Excel con vista previa y revisión antes de guardar.
- Panel de productividad con filtros por fecha, sector y labor.
- Pagos semanales: se fija el precio por kilo de la semana, el sistema calcula lo que corresponde a cada trabajador y la semana se puede cerrar (el cierre no se puede deshacer).
- Reportes de producción y de pagos, con descarga en CSV e impresión en PDF.
- Análisis con IA: perfiles de productividad (K-Means), registros atípicos (Isolation Forest) y una estimación de la próxima jornada (Random Forest).
- Asistente conversacional que responde preguntas sobre los datos usando una API de OpenAI.

Es un prototipo funcional. No tiene inicio de sesión ni roles, y el modelo de predicción todavía se apoya en pocos datos (385 registros de 10 semanas), así que sus resultados son orientativos.

## Tecnologías

- Backend: Python, FastAPI y psycopg, sin ORM.
- Base de datos: PostgreSQL.
- Frontend: React 19 y Vite.
- Datos e IA: pandas, scikit-learn y OpenAI.
- Metodología: Scrum para el desarrollo y CRISP-DM para la parte de datos.

## Estructura del repositorio

```
FASE 1/                       Documentos y evidencias de la Fase 1
FASE 2/
  2.4_GuiaEstudiante_...docx  Informe de avance de la Fase 2
  Evidencias Individuales/    Diarios de cada integrante
  DonaLaura/
    backend/                  API en FastAPI
      main.py                 trabajadores, producción, productividad e importación
      pagos.py                tarifas y pagos semanales
      reportes.py             reportes y exportación
      ia/                     modelo de productividad, herramientas y asistente
      esquema.sql             script para crear la base de datos
      .env.example            plantilla de variables de entorno
    frontend/                 aplicación React
```

## Cómo correrlo

Necesitas Python 3, Node.js y PostgreSQL instalados.

### 1. Base de datos

Desde la carpeta `FASE 2/DonaLaura/backend`:

```
psql -U postgres -c "CREATE DATABASE dona_laura_db"
psql -U postgres -d dona_laura_db -f esquema.sql
```

### 2. Backend

Siempre en `backend`:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements_ia.txt
copy .env.example .env
```

Abre el archivo `.env` y completa la clave de PostgreSQL. La clave de OpenAI solo hace falta para el asistente conversacional, y cada pregunta que se le hace consume crédito de esa cuenta. Después:

```
uvicorn main:app --reload
```

La API queda en http://127.0.0.1:8000 y la documentación interactiva en http://127.0.0.1:8000/docs.

### 3. Frontend

En otra terminal, dentro de `FASE 2/DonaLaura/frontend`:

```
npm install
npm run dev
```

La aplicación se abre en http://localhost:5173. Hay que usar `localhost`, con `127.0.0.1` no carga.

## Sobre los datos de ejemplo

El archivo `backend/ia/dataset_cosecha_paltas_2026.csv` viene con los trabajadores anonimizados (`T-01`, `T-02`, ...) para no publicar nombres reales. Si quieres que el análisis use otro CSV, por ejemplo uno con nombres, escribe su ruta en la variable `DATASET_PATH` del `.env`. Si la variable no está, se usa el archivo del repositorio.

## Equipo

- Sebastián Valenzuela
- Alex Núñez
- Alexander Vivanco
- Diego Álvarez

Profesor guía: Cristian Molina Pedernera.
