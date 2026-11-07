CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario VARCHAR(80) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    password_hash TEXT NOT NULL,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('administrador', 'encargado', 'consulta')),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS sesiones (
    token_hash TEXT PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    vence_en TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sesiones_vencimiento ON sesiones(vence_en);
CREATE TABLE IF NOT EXISTS auditoria (
    id_evento BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario INTEGER REFERENCES usuarios(id_usuario),
    accion VARCHAR(180) NOT NULL,
    detalle VARCHAR(250) NOT NULL DEFAULT '',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS intentos_login (
    usuario VARCHAR(80) NOT NULL,
    origen VARCHAR(80) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS intentos_login_busqueda ON intentos_login(usuario, origen, creado_en);
