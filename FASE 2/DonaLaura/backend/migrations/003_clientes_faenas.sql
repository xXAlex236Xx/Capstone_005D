CREATE TABLE clientes (
    id_cliente INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(160) NOT NULL CHECK (length(btrim(nombre)) >= 2),
    contacto VARCHAR(120) NOT NULL DEFAULT '',
    email VARCHAR(180) NOT NULL DEFAULT '',
    telefono VARCHAR(40) NOT NULL DEFAULT '',
    notas VARCHAR(1000) NOT NULL DEFAULT '',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX clientes_nombre_unico ON clientes (lower(btrim(nombre)));

CREATE TABLE faenas (
    id_faena INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
    nombre VARCHAR(160) NOT NULL CHECK (length(btrim(nombre)) >= 2),
    predio VARCHAR(160) NOT NULL CHECK (length(btrim(predio)) >= 2),
    cultivo VARCHAR(100) NOT NULL DEFAULT '',
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE,
    precio_kg NUMERIC(12,2) NOT NULL CHECK (precio_kg > 0),
    estado VARCHAR(20) NOT NULL DEFAULT 'Planificada'
        CHECK (estado IN ('Planificada','Activa','Finalizada')),
    notas VARCHAR(1000) NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);
CREATE UNIQUE INDEX faenas_nombre_fecha_unico ON faenas (id_cliente,lower(btrim(nombre)),fecha_inicio);
ALTER TABLE produccion ADD COLUMN id_faena INTEGER REFERENCES faenas(id_faena);
CREATE INDEX produccion_faena_idx ON produccion(id_faena) WHERE id_faena IS NOT NULL;
CREATE INDEX faenas_cliente_idx ON faenas(id_cliente);
CREATE INDEX IF NOT EXISTS ajustes_produccion_idx ON ajustes_cosecha(id_produccion);
