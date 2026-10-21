-- =====================================================
-- ESQUEMA DE LA BASE DE DATOS: dona_laura_db
-- =====================================================
-- Crea las 7 tablas del sistema en una base vacía.
--
-- Uso (desde la carpeta backend):
--   1. Crear la base:   psql -U postgres -c "CREATE DATABASE dona_laura_db"
--   2. Cargar el esquema: psql -U postgres -d dona_laura_db -f esquema.sql
--
-- Después, completar los datos de conexión en el archivo .env
-- (ver .env.example). El script se puede ejecutar más de una vez:
-- las tablas que ya existen no se modifican.
-- =====================================================


-- =====================================================
-- TABLAS BASE
-- =====================================================

CREATE TABLE IF NOT EXISTS trabajadores (
    id_trabajador INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    rut VARCHAR(12) UNIQUE,
    estado VARCHAR(20) NOT NULL DEFAULT 'Activo'
        CHECK (estado IN ('Activo', 'Inactivo'))
);

CREATE TABLE IF NOT EXISTS jornadas (
    id_jornada INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha DATE NOT NULL UNIQUE,
    observaciones TEXT
);

CREATE TABLE IF NOT EXISTS sectores (
    id_sector INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS labores (
    id_labor INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);


-- =====================================================
-- PRODUCCIÓN
-- =====================================================

CREATE TABLE IF NOT EXISTS produccion (
    id_produccion INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_trabajador INTEGER NOT NULL REFERENCES trabajadores (id_trabajador),
    id_jornada INTEGER NOT NULL REFERENCES jornadas (id_jornada),
    id_sector INTEGER NOT NULL REFERENCES sectores (id_sector),
    id_labor INTEGER NOT NULL REFERENCES labores (id_labor),
    cantidad_kg NUMERIC(10, 2) NOT NULL CHECK (cantidad_kg >= 0),
    horas_trabajadas NUMERIC(5, 2)
        CHECK (horas_trabajadas > 0 AND horas_trabajadas <= 24)
);


-- =====================================================
-- PAGOS Y TARIFAS
-- =====================================================
-- Estas dos tablas también las crea el backend al iniciar
-- (ver pagos.py). Se incluyen aquí para tener el esquema completo.

CREATE TABLE IF NOT EXISTS tarifas (
    id_tarifa SERIAL PRIMARY KEY,
    semana_inicio DATE NOT NULL UNIQUE,
    precio_kg NUMERIC(10, 2) NOT NULL CHECK (precio_kg > 0),
    creado_en TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pagos (
    id_pago SERIAL PRIMARY KEY,
    semana_inicio DATE NOT NULL,
    id_trabajador INTEGER NOT NULL REFERENCES trabajadores (id_trabajador),
    kilos NUMERIC(12, 2) NOT NULL,
    precio_kg NUMERIC(10, 2) NOT NULL,
    total NUMERIC(14, 0) NOT NULL,
    fecha_cierre TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (semana_inicio, id_trabajador)
);
