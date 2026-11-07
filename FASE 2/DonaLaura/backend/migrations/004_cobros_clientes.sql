CREATE TABLE cobros_cliente (
    id_cobro BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave UUID NOT NULL UNIQUE,
    contenido_hash TEXT NOT NULL,
    id_faena INTEGER NOT NULL REFERENCES faenas(id_faena),
    fecha_acuerdo DATE NOT NULL,
    vencimiento DATE NOT NULL,
    monto NUMERIC(14,0) NOT NULL CHECK(monto > 0),
    kilos_referencia NUMERIC(18,2) NOT NULL,
    precio_referencia NUMERIC(12,2) NOT NULL,
    estimado_referencia NUMERIC(18,0) NOT NULL,
    concepto VARCHAR(500) NOT NULL,
    estado VARCHAR(12) NOT NULL DEFAULT 'Vigente' CHECK(estado IN ('Vigente','Anulado')),
    motivo_anulacion VARCHAR(500),
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(vencimiento >= fecha_acuerdo)
);
CREATE UNIQUE INDEX cobro_vigente_faena ON cobros_cliente(id_faena) WHERE estado='Vigente';
CREATE INDEX cobros_vencimiento_idx ON cobros_cliente(vencimiento) WHERE estado='Vigente';
CREATE TABLE abonos_cliente (
    id_abono BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave UUID NOT NULL UNIQUE,
    id_cobro BIGINT NOT NULL REFERENCES cobros_cliente(id_cobro),
    monto NUMERIC(14,0) NOT NULL CHECK(monto > 0),
    fecha DATE NOT NULL,
    referencia VARCHAR(180) NOT NULL CHECK(length(btrim(referencia)) >= 3),
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX abono_cliente_referencia ON abonos_cliente(id_cobro,lower(btrim(referencia)));
