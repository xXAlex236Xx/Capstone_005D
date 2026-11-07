"""Consultas agregadas de solo lectura para el asistente de gestión."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from database import conectar_bd
from entorno import describir_entorno
from cobros import resumen_cobros, cartera_por_cliente


def pesos(valor):
    return int(Decimal(valor or 0).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def consultar_gestion(fecha_desde: str | None = None, fecha_hasta: str | None = None):
    desde = date.fromisoformat(fecha_desde) if fecha_desde else None
    hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else None
    if desde and hasta and desde > hasta:
        return {"error": "La fecha inicial debe ser anterior a la final"}
    with conectar_bd() as conexion:
        conexion.execute("SET TRANSACTION READ ONLY")
        cobranza = resumen_cobros(conexion)
        cartera = cartera_por_cliente(conexion)
        rango = conexion.execute("SELECT MIN(fecha),MAX(fecha) FROM jornadas WHERE id_jornada IN (SELECT id_jornada FROM produccion)").fetchone()
        perfiles = conexion.execute("SELECT rol,COUNT(*) FROM usuarios WHERE activo GROUP BY rol ORDER BY rol").fetchall()
        desde = desde or rango[0]
        hasta = hasta or rango[1]
        if not desde or not hasta:
            return {"entorno": describir_entorno(), "mensaje": "No hay producción registrada"}
        clientes = conexion.execute("""SELECT COALESCE(c.nombre,'Sin cliente vinculado'),
            COUNT(DISTINCT f.id_faena),SUM(p.cantidad_kg+COALESCE(a.kilos,0)),
            SUM((p.cantidad_kg+COALESCE(a.kilos,0))*f.precio_kg)
            FROM produccion p JOIN jornadas j USING(id_jornada)
            LEFT JOIN faenas f USING(id_faena) LEFT JOIN clientes c USING(id_cliente)
            LEFT JOIN LATERAL(SELECT SUM(diferencia_kg) AS kilos FROM ajustes_cosecha
                WHERE id_produccion=p.id_produccion) a ON TRUE
            WHERE j.fecha BETWEEN %s AND %s GROUP BY c.id_cliente,c.nombre
            ORDER BY 3 DESC LIMIT 20""", (desde,hasta)).fetchall()
        meses = conexion.execute("""SELECT to_char(j.fecha,'YYYY-MM'),SUM(p.cantidad_kg+COALESCE(a.kilos,0)),
            COUNT(DISTINCT j.fecha),COUNT(DISTINCT p.id_trabajador)
            FROM produccion p JOIN jornadas j USING(id_jornada)
            LEFT JOIN LATERAL(SELECT SUM(diferencia_kg) AS kilos FROM ajustes_cosecha
                WHERE id_produccion=p.id_produccion) a ON TRUE
            WHERE j.fecha BETWEEN %s AND %s GROUP BY 1 ORDER BY 1 DESC LIMIT 36""",(desde,hasta)).fetchall()
        activos = conexion.execute("""SELECT f.nombre,c.nombre,f.predio,f.cultivo,f.precio_kg,f.fecha_inicio,f.fecha_fin
            FROM faenas f JOIN clientes c USING(id_cliente) WHERE f.estado='Activa'
            ORDER BY f.fecha_inicio DESC,f.id_faena DESC LIMIT 20""").fetchall()
        pagos = conexion.execute("""SELECT COUNT(*),COALESCE(SUM(g.total+COALESCE(a.monto,0)),0),
            COALESCE(SUM(COALESCE(b.monto,0)),0),
            COUNT(*) FILTER(WHERE g.total+COALESCE(a.monto,0)>COALESCE(b.monto,0))
            FROM pagos g LEFT JOIN LATERAL(SELECT SUM(monto) AS monto FROM ajustes_cosecha WHERE id_pago=g.id_pago) a ON TRUE
            LEFT JOIN LATERAL(SELECT SUM(monto) AS monto FROM abonos_pago WHERE id_pago=g.id_pago) b ON TRUE
            WHERE g.semana_inicio BETWEEN date_trunc('week',%s::date)::date AND date_trunc('week',%s::date)::date""",(desde,hasta)).fetchone()
        totales = conexion.execute("""SELECT COUNT(*),COUNT(DISTINCT p.id_trabajador),COUNT(DISTINCT j.fecha),
            COALESCE(SUM(p.cantidad_kg+COALESCE(a.kilos,0)),0),
            COALESCE(SUM((p.cantidad_kg+COALESCE(a.kilos,0))*f.precio_kg),0),
            COUNT(*) FILTER(WHERE f.id_faena IS NULL)
            FROM produccion p JOIN jornadas j USING(id_jornada) LEFT JOIN faenas f USING(id_faena)
            LEFT JOIN LATERAL(SELECT SUM(diferencia_kg) AS kilos FROM ajustes_cosecha WHERE id_produccion=p.id_produccion) a ON TRUE
            WHERE j.fecha BETWEEN %s AND %s""",(desde,hasta)).fetchone()
    return {"entorno": describir_entorno(), "cobros_clientes_actuales_sin_filtro_de_produccion": cobranza, "cartera_actual_por_cliente":cartera, "periodo_produccion": {"desde":desde.isoformat(),"hasta":hasta.isoformat()},
        "usuarios_activos_por_perfil":dict(perfiles),
        "resumen": {"registros":totales[0],"trabajadores_con_produccion":totales[1],"dias_con_produccion":totales[2],
                    "kilos_incluidos_ajustes":float(totales[3]),"cobro_estimado_faenas_clp":pesos(totales[4]),"registros_sin_faena":totales[5]},
        "clientes_por_volumen_hasta_20": [{"cliente":n,"faenas_con_produccion":f,"kilos":float(k),
            "cobro_estimado_clp":pesos(m) if m is not None else None} for n,f,k,m in clientes],
        "ultimos_36_meses": [{"mes":m,"kilos":float(k),"dias_con_produccion":d,"trabajadores":t} for m,k,d,t in meses],
        "faenas_activas_actuales_hasta_20": [dict(zip(("faena","cliente","predio","cultivo","precio_cliente_clp_kg","inicio","fin"),fila)) for fila in activos],
        "pagos_trabajadores": {"cierres_individuales":pagos[0],"total_bruto_clp":pesos(pagos[1]),"abonado_clp":pesos(pagos[2]),
            "saldo_clp":pesos(pagos[1]-pagos[2]),"cierres_con_saldo":pagos[3],
            "alcance":"Cierres de semanas cuyo lunes está entre las semanas de inicio y fin del período. Incluye la semana completa; excluye producción todavía sin cierre."},
        "limites":"Cobro al cliente es estimado: no es dinero recibido ni utilidad, no agrega impuestos. Pagos_trabajadores son egresos. Cobros_clientes_actuales_sin_filtro_de_produccion contiene acuerdos confirmados, abonos recibidos y saldos actuales de todos los cobros vigentes, sin aplicar el período de producción; recibido es lo anotado por el usuario, no verificación bancaria. No restes estos saldos de períodos diferentes para inventar utilidad. Los kilos incluyen ajustes de semanas cerradas; el análisis predictivo usa registros originales agrupados, por lo que sus totales pueden diferir. Faenas activas corresponden al estado actual, sin filtro temporal. No se han registrado transporte, insumos u otros costos."}
