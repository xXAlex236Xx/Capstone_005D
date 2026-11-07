from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from database import conectar_bd
from cobros import resumen_cobros

router = APIRouter(tags=["Resumen"])


@router.get("/mi-dia")
def mi_dia(fecha: date | None = None):
    hoy = fecha or datetime.now(ZoneInfo("America/Santiago")).date()
    lunes = hoy - timedelta(days=hoy.weekday())
    with conectar_bd() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        registros, personas, kilos = c.execute("""SELECT COUNT(*),COUNT(DISTINCT p.id_trabajador),COALESCE(SUM(p.cantidad_kg),0)
            FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha=%s""", (hoy,)).fetchone()
        ultima = c.execute("SELECT MAX(j.fecha) FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha<=%s", (hoy,)).fetchone()[0]
        semanas = [r[0] for r in c.execute("""SELECT DISTINCT date_trunc('week',j.fecha)::date AS semana
            FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha<%s
            AND NOT EXISTS(SELECT 1 FROM pagos g WHERE g.semana_inicio=date_trunc('week',j.fecha)::date)
            ORDER BY semana""", (lunes,)).fetchall()]
        saldo, pendientes, por_aprobar = c.execute("""WITH saldos AS (
            SELECT g.id_pago,g.total+COALESCE(a.monto,0)-COALESCE(b.monto,0) AS saldo,
                EXISTS(SELECT 1 FROM aprobaciones_pago ap WHERE ap.id_pago=g.id_pago) AS aprobado
            FROM pagos g LEFT JOIN (SELECT id_pago,SUM(monto) monto FROM ajustes_cosecha GROUP BY id_pago) a USING(id_pago)
            LEFT JOIN (SELECT id_pago,SUM(monto) monto FROM abonos_pago GROUP BY id_pago) b USING(id_pago))
            SELECT COALESCE(SUM(saldo) FILTER(WHERE saldo>0),0),COUNT(*) FILTER(WHERE saldo>0),
                COUNT(*) FILTER(WHERE saldo>0 AND NOT aprobado) FROM saldos""").fetchone()
        faenas = c.execute("""SELECT f.id_faena,f.nombre,cl.nombre,f.predio,f.fecha_fin,
            (SELECT COUNT(*) FROM produccion p JOIN jornadas j USING(id_jornada) WHERE p.id_faena=f.id_faena AND j.fecha=%s)
            FROM faenas f JOIN clientes cl USING(id_cliente) WHERE cl.activo AND f.estado='Activa'
            AND f.fecha_inicio<=%s AND (f.fecha_fin IS NULL OR f.fecha_fin>=%s) ORDER BY f.fecha_fin NULLS LAST,f.id_faena""", (hoy,hoy,hoy)).fetchall()
        proximas = c.execute("""SELECT f.nombre,c.nombre,f.fecha_inicio,f.estado FROM faenas f JOIN clientes c USING(id_cliente)
            WHERE c.activo AND f.estado IN ('Planificada','Activa') AND f.fecha_inicio>%s AND f.fecha_inicio<=%s
            ORDER BY f.fecha_inicio,f.id_faena LIMIT 8""", (hoy,hoy+timedelta(days=7))).fetchall()
        cobros = resumen_cobros(c,hoy)
    return {"fecha":hoy,"cobros_clientes":cobros,"registros_hoy":registros,"personas_hoy":personas,"kilos_hoy":kilos,"ultima_produccion":ultima,
        "semanas_por_cerrar":len(semanas),"primeras_semanas":semanas[:5],
        "saldo_trabajadores":saldo,"pagos_con_saldo":pendientes,"pagos_por_aprobar":por_aprobar,
        "faenas":[dict(zip(("id","nombre","cliente","predio","fecha_fin","registros_hoy"),f)) for f in faenas],
        "proximas":[dict(zip(("nombre","cliente","fecha_inicio","estado"),f)) for f in proximas]}


@router.get("/resumen")
def resumen():
    with conectar_bd() as conexion:
        activos = conexion.execute("SELECT COUNT(*) FROM trabajadores WHERE estado='Activo'").fetchone()[0]
        ultima = conexion.execute("SELECT MAX(j.fecha) FROM produccion p JOIN jornadas j USING(id_jornada)").fetchone()[0]
        if ultima is None:
            return {"activos": activos, "desde": None, "hasta": None, "kilos": 0, "horas": 0,
                    "variacion": None, "semanas_pendientes": 0, "dias": [], "trabajadores": [], "sectores": []}
        desde = ultima - timedelta(days=6)
        kilos, horas = conexion.execute("""SELECT COALESCE(SUM(p.cantidad_kg),0),COALESCE(SUM(p.horas_trabajadas),0)
            FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha BETWEEN %s AND %s""", (desde, ultima)).fetchone()
        anterior = conexion.execute("SELECT COALESCE(SUM(p.cantidad_kg),0) FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha >= %s AND j.fecha < %s", (desde-timedelta(days=7), desde)).fetchone()[0]
        dias = dict(conexion.execute("SELECT j.fecha,SUM(p.cantidad_kg) FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha BETWEEN %s AND %s GROUP BY j.fecha", (desde, ultima)).fetchall())
        personas = conexion.execute("""SELECT t.id_trabajador,t.nombre,t.apellido,SUM(p.cantidad_kg),SUM(p.horas_trabajadas)
            FROM produccion p JOIN trabajadores t USING(id_trabajador) JOIN jornadas j USING(id_jornada)
            WHERE j.fecha BETWEEN %s AND %s GROUP BY t.id_trabajador,t.nombre,t.apellido ORDER BY SUM(p.cantidad_kg) DESC LIMIT 5""", (desde, ultima)).fetchall()
        sectores = conexion.execute("""SELECT s.nombre,SUM(p.cantidad_kg) FROM produccion p JOIN sectores s USING(id_sector)
            JOIN jornadas j USING(id_jornada) WHERE j.fecha BETWEEN %s AND %s GROUP BY s.nombre ORDER BY SUM(p.cantidad_kg) DESC""", (desde, ultima)).fetchall()
        pendientes = conexion.execute("""SELECT COUNT(DISTINCT date_trunc('week',j.fecha))
            FROM produccion p JOIN jornadas j USING(id_jornada)
            WHERE NOT EXISTS (SELECT 1 FROM pagos g WHERE g.semana_inicio=date_trunc('week',j.fecha)::date)""").fetchone()[0]
    return {
        "activos": activos, "desde": desde, "hasta": ultima, "kilos": float(kilos), "horas": float(horas),
        "variacion": round(float((kilos-anterior)/anterior*100),1) if anterior else None,
        "semanas_pendientes": pendientes,
        "dias": [{"fecha": desde+timedelta(days=i), "kilos": float(dias.get(desde+timedelta(days=i),0))} for i in range(7)],
        "trabajadores": [{"id": f[0], "nombre": f"{f[1]} {f[2]}", "kilos": float(f[3]), "horas": float(f[4] or 0)} for f in personas],
        "sectores": [{"nombre": f[0], "kilos": float(f[1])} for f in sectores],
    }
