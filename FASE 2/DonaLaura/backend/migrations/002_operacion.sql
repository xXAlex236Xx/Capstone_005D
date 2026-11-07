ALTER TABLE produccion ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS lotes_cosecha (
    clave UUID PRIMARY KEY,
    contenido_hash TEXT NOT NULL,
    resultado JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS correcciones_cosecha (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_produccion INTEGER NOT NULL REFERENCES produccion(id_produccion),
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    motivo TEXT NOT NULL,
    antes JSONB NOT NULL,
    despues JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS aprobaciones_pago (
    id_pago INTEGER PRIMARY KEY REFERENCES pagos(id_pago),
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    aprobado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS abonos_pago (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave UUID NOT NULL UNIQUE,
    id_pago INTEGER NOT NULL REFERENCES pagos(id_pago),
    monto NUMERIC(14,0) NOT NULL CHECK(monto>0),
    fecha DATE NOT NULL,
    comprobante VARCHAR(180) NOT NULL,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS ajustes_cosecha (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave UUID NOT NULL UNIQUE,
    id_produccion INTEGER NOT NULL REFERENCES produccion(id_produccion),
    id_pago INTEGER NOT NULL REFERENCES pagos(id_pago),
    diferencia_kg NUMERIC(10,2) NOT NULL,
    diferencia_horas NUMERIC(5,2) NOT NULL,
    monto NUMERIC(14,0) NOT NULL,
    motivo TEXT NOT NULL,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
