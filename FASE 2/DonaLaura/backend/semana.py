"""Revisión semanal de solo lectura; nunca cierra ni registra pagos automáticamente."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import Response
from database import conectar_bd
from pagos import lunes_de, calcular_total
from cobros import resumen_cobros, cartera_por_cliente

router = APIRouter(tags=["Preparar la semana"])


def consultar_semana(fecha: date | None = None):
    hoy = datetime.now(ZoneInfo("America/Santiago")).date()
    desde = lunes_de(fecha or hoy-timedelta(days=7))
    hasta = desde+timedelta(days=6)
    with conectar_bd() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        filas = c.execute("""SELECT j.fecha,COUNT(*),COUNT(DISTINCT p.id_trabajador),SUM(p.cantidad_kg),
            COALESCE(SUM(p.horas_trabajadas),0),SUM(COALESCE(a.kilos,0)),SUM(COALESCE(a.horas,0))
            FROM produccion p JOIN jornadas j USING(id_jornada)
            LEFT JOIN LATERAL(SELECT SUM(diferencia_kg) kilos,SUM(diferencia_horas) horas
                FROM ajustes_cosecha WHERE id_produccion=p.id_produccion) a ON TRUE
            WHERE j.fecha BETWEEN %s AND %s GROUP BY j.fecha ORDER BY j.fecha""",(desde,hasta)).fetchall()
        personas = c.execute("""SELECT p.id_trabajador,SUM(p.cantidad_kg) FROM produccion p JOIN jornadas j USING(id_jornada)
            WHERE j.fecha BETWEEN %s AND %s GROUP BY p.id_trabajador""",(desde,hasta)).fetchall()
        tarifa = c.execute("SELECT precio_kg FROM tarifas WHERE semana_inicio=%s",(desde,)).fetchone()
        pagos = c.execute("""SELECT COUNT(*),COALESCE(SUM(g.total+COALESCE(a.monto,0)),0),COALESCE(SUM(b.monto),0)
            FROM pagos g LEFT JOIN LATERAL(SELECT SUM(monto) monto FROM ajustes_cosecha WHERE id_pago=g.id_pago) a ON TRUE
            LEFT JOIN LATERAL(SELECT SUM(monto) monto FROM abonos_pago WHERE id_pago=g.id_pago) b ON TRUE
            WHERE g.semana_inicio=%s""",(desde,)).fetchone()
        sin_faena, invalidos = c.execute("""SELECT COUNT(*) FILTER(WHERE p.id_faena IS NULL),
            COUNT(*) FILTER(WHERE p.horas_trabajadas IS NULL OR p.horas_trabajadas<=0 OR p.cantidad_kg<0)
            FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha BETWEEN %s AND %s""",(desde,hasta)).fetchone()
        duplicados = c.execute("""SELECT COUNT(*) FROM (SELECT p.id_trabajador,p.id_jornada,p.id_sector,p.id_labor,p.id_faena
            FROM produccion p JOIN jornadas j USING(id_jornada) WHERE j.fecha BETWEEN %s AND %s
            GROUP BY 1,2,3,4,5 HAVING COUNT(*)>1) d""",(desde,hasta)).fetchone()[0]
        horas_exceso = c.execute("""SELECT COUNT(*) FROM (SELECT p.id_trabajador,j.fecha FROM produccion p
            JOIN jornadas j USING(id_jornada) WHERE j.fecha BETWEEN %s AND %s GROUP BY 1,2
            HAVING SUM(p.horas_trabajadas)>24) d""",(desde,hasta)).fetchone()[0]
        faenas = c.execute("""SELECT COALESCE(cl.nombre,'Sin cliente vinculado'),COALESCE(f.nombre,'Sin faena'),
            SUM(p.cantidad_kg+COALESCE(a.kilos,0)),SUM((p.cantidad_kg+COALESCE(a.kilos,0))*f.precio_kg)
            FROM produccion p JOIN jornadas j USING(id_jornada) LEFT JOIN faenas f USING(id_faena)
            LEFT JOIN clientes cl USING(id_cliente) LEFT JOIN LATERAL(SELECT SUM(diferencia_kg) kilos
                FROM ajustes_cosecha WHERE id_produccion=p.id_produccion) a ON TRUE
            WHERE j.fecha BETWEEN %s AND %s GROUP BY f.id_faena,cl.nombre,f.nombre ORDER BY 3 DESC""",(desde,hasta)).fetchall()
        recibido = c.execute("SELECT COALESCE(SUM(monto),0) FROM abonos_cliente WHERE fecha BETWEEN %s AND %s",(desde,hasta)).fetchone()[0]
        pagado = c.execute("SELECT COALESCE(SUM(monto),0) FROM abonos_pago WHERE fecha BETWEEN %s AND %s",(desde,hasta)).fetchone()[0]
        confirmados = c.execute("SELECT COUNT(*),COALESCE(SUM(monto),0) FROM cobros_cliente WHERE estado='Vigente' AND fecha_acuerdo BETWEEN %s AND %s",(desde,hasta)).fetchone()
        cartera = resumen_cobros(c,hoy)
        clientes = cartera_por_cliente(c)
        es_demo = bool(c.execute("SELECT to_regclass('public.entorno_demostracion')").fetchone()[0])
    precio = tarifa[0] if tarifa else None
    cerrada = pagos[0]>0
    estimado = sum((calcular_total(k,precio) for _,k in personas if k>0),Decimal(0)) if precio is not None else None
    alertas=[]
    def agregar(clave, cantidad, mensaje, bloquea=False):
        if cantidad: alertas.append({"clave":clave,"cantidad":cantidad,"mensaje":mensaje,"bloquea":bloquea})
    agregar("datos",invalidos,"Registros con kilos negativos u horas vacías o no positivas. Revisa sus datos.",True)
    agregar("duplicados",duplicados,"Grupos con registros repetidos para persona, fecha, sector, labor y faena. Revisa el historial.",True)
    agregar("horas",horas_exceso,"Personas con más de 24 horas acumuladas en un día. Revisa las jornadas.",True)
    agregar("faenas",sin_faena,"Registros sin faena: sus kilos no generan un estimado de cobro al cliente.")
    agregar("tarifa",bool(personas and precio is None and not cerrada),"Falta la tarifa semanal para estimar los pagos.",True)
    agregar("sin_kilos",bool(personas and not any(k>0 for _,k in personas) and not cerrada),"No hay kilos positivos para generar un cierre de pagos.",True)
    if hasta>=hoy and not cerrada: agregar("en_curso",1,"La semana aún no terminó. Puedes revisarla, pero conviene completar sus jornadas antes de cerrar.")
    if any(f[0]>hoy for f in filas): agregar("futuro",1,"Hay producción con fecha futura. Revisa las fechas antes del cierre.",True)
    return {"desde":desde,"hasta":hasta,"fecha_consulta":hoy,"demostracion":es_demo,
        "registros":sum(f[1] for f in filas),"personas":len(personas),"dias_con_registros":len(filas),
        "kilos_originales":sum((f[3] for f in filas),Decimal(0)),"ajustes_kg":sum((f[5] for f in filas),Decimal(0)),
        "kilos":sum((f[3]+f[5] for f in filas),Decimal(0)),"horas":sum((f[4]+f[6] for f in filas),Decimal(0)),
        "dias":[dict(zip(("fecha","registros","personas","kilos_originales","horas_originales","ajustes_kg","ajustes_horas"),f)) for f in filas],
        "precio_kg":precio,"cerrada":cerrada,"pago_estimado":estimado,"pago_confirmado":pagos[1] if cerrada else None,
        "saldo_cierres_semana":pagos[1]-pagos[2] if cerrada else None,
        "recibido_clientes_periodo":recibido,"abonado_trabajadores_periodo":pagado,
        "acuerdos_periodo":confirmados[0],"monto_acuerdos_periodo":confirmados[1],
        "cartera_actual":cartera,"clientes_con_saldo_actual":[f for f in clientes if f["saldo_clp"]>0],
        "faenas":[dict(zip(("cliente","faena","kilos","cobro_estimado"),f)) for f in faenas],"alertas":alertas,
        "listo_para_revisar_cierre":bool(personas and not cerrada and hasta<hoy and not any(a["bloquea"] for a in alertas))}


@router.get("/preparar-semana")
def preparar_semana(fecha: date | None = None):
    return consultar_semana(fecha)


@router.get("/preparar-semana/pdf")
def descargar_semana(fecha: date | None = None):
    from semana_pdf import generar_pdf
    datos = consultar_semana(fecha)
    return Response(generar_pdf(datos),media_type="application/pdf",headers={
        "Content-Disposition":f'attachment; filename="Agricolix_resumen_{datos["desde"].isoformat()}.pdf"',"Cache-Control":"no-store"})
