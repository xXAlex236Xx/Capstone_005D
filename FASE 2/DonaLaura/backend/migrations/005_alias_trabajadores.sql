-- Nombres con que un trabajador aparece escrito en las planillas Excel.
-- Se llena cuando quien importa confirma que dos nombres son la misma persona,
-- para no volver a preguntar en las próximas importaciones.
CREATE TABLE IF NOT EXISTS alias_trabajadores (
    alias VARCHAR(160) PRIMARY KEY,
    id_trabajador INTEGER NOT NULL REFERENCES trabajadores(id_trabajador),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
