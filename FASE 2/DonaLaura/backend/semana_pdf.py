"""Resumen ejecutivo de una página, generado desde la misma consulta que la interfaz."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth


def numero(n, dec=0):
    return f"{float(n):,.{dec}f}".replace(",","_").replace(".",",").replace("_",".")


def pesos(n):
    return "Por definir" if n is None else "$"+numero(n)


def fecha(d):
    return d.strftime("%d-%m-%Y")


def generar_pdf(d):
    salida=BytesIO()
    c=canvas.Canvas(salida,pagesize=A4)
    c.setTitle(f"Agricolix - Resumen semanal {d['desde']}")
    c.setAuthor("Doña Laura SpA - Agricolix")
    ancho,alto=A4
    verde="#234E3B"; texto="#3C5145"; gris="#738275"
    def escribir(x,y,t,tamano=10,color=texto,negrita=False):
        c.setFillColor(HexColor(color)); c.setFont("Helvetica-Bold" if negrita else "Helvetica",tamano); c.drawString(x,y,str(t))
    def parrafo(x,y,t,w,tamano=8,max_alto=40):
        estilo=ParagraphStyle("p",fontName="Helvetica",fontSize=tamano,leading=tamano+3,textColor=HexColor(gris))
        p=Paragraph(escape(str(t)),estilo); _,h=p.wrap(w,max_alto)
        if h>max_alto:
            # Acota notas extensas para conservar la página y remite al detalle de la aplicación.
            t=str(t)
            while h>max_alto and len(t)>10:
                t=t[:-12]; p=Paragraph(escape(t)+"...",estilo); _,h=p.wrap(w,max_alto)
        p.drawOn(c,x,y-h)
    def corto(t,w,tamano=8):
        t=str(t)
        while stringWidth(t,"Helvetica",tamano)>w and len(t)>3: t=t[:-4]+"..."
        return t
    def titulo(y,t):
        escribir(36,y,t,11,verde,True); c.setStrokeColor(HexColor("#DCE5D8")); c.line(36,y-9,ancho-36,y-9)
    c.setFillColor(HexColor(verde)); c.rect(0,alto-108,ancho,108,fill=1,stroke=0)
    escribir(36,alto-30,"agricolix.  /  DOÑA LAURA SpA",12,"#DCEACB",True)
    escribir(36,alto-58,"Resumen semanal del dueño",23,"#FFFFFF",True)
    escribir(36,alto-82,f"{fecha(d['desde'])} al {fecha(d['hasta'])}  |  Consulta: {fecha(d['fecha_consulta'])}",10,"#D9E6D7")
    etiqueta="DEMOSTRACIÓN - DATOS FICTICIOS" if d["demostracion"] else "RESUMEN DE GESTIÓN - REGISTROS DEL SISTEMA"
    escribir(36,alto-130,etiqueta,9,"#9A773B" if d["demostracion"] else gris,True)
    pago=d["pago_confirmado"] if d["cerrada"] else d["pago_estimado"]
    tarjetas=[("PRODUCCIÓN DE LA SEMANA",numero(d["kilos"],2)+" kg",f"{d['personas']} personas / {d['dias_con_registros']} días con registros"),
        ("PAGOS DE ESA SEMANA" if d["cerrada"] else "PAGOS ESTIMADOS / SIN CIERRE",pesos(pago),"Incluye ajustes del cierre" if d["cerrada"] else "Según tarifa y kilos originales; sujeto a revisión"),
        ("RECIBIDO DE CLIENTES EN EL PERÍODO",pesos(d["recibido_clientes_periodo"]),"Por fecha de recepción anotada"),
        ("ABONADO A TRABAJADORES EN EL PERÍODO",pesos(d["abonado_trabajadores_periodo"]),"Por fecha de abono; puede corresponder a otras semanas")]
    for i,(t,v,n) in enumerate(tarjetas):
        x=36+(i%2)*267; y=alto-211-(i//2)*78
        c.setFillColor(HexColor("#F1F5EC")); c.roundRect(x,y,255,67,7,fill=1,stroke=0)
        escribir(x+12,y+51,t,7,gris,True); escribir(x+12,y+27,v,19,verde,True); parrafo(x+12,y+16,n,232,7,20)
    titulo(509,"01 / Revisión y cierre")
    estado="Cierre de pagos confirmado" if d["cerrada"] else "Pendiente de revisar y confirmar en Pagos"
    escribir(36,482,estado,10,verde,True)
    texto_alertas="Sin alertas automáticas en los controles revisados. Contrasta la asistencia, los pesajes y los comprobantes."
    if d["alertas"]:
        texto_alertas=" | ".join(f"{a['cantidad']}: {a['mensaje']}" for a in d["alertas"][:3])
        if len(d["alertas"])>3: texto_alertas+=" Más alertas en Preparar la semana."
    parrafo(36,470,texto_alertas,ancho-72,8,43)
    titulo(408,f"02 / Producción por faena ({min(4,len(d['faenas']))} de {len(d['faenas'])})")
    escribir(36,384,"CLIENTE / FAENA",7,gris,True); escribir(332,384,"KILOS",7,gris,True); escribir(422,384,"COBRO ESTIMADO",7,gris,True)
    for i,f in enumerate(d["faenas"][:4]):
        y=365-i*29
        escribir(36,y,corto(f["cliente"],280),8)
        escribir(36,y-11,corto(f["faena"],280),7,gris)
        escribir(332,y,numero(f["kilos"],2),9)
        escribir(422,y,pesos(f["cobro_estimado"]),9)
    if not d["faenas"]: escribir(36,360,"Sin producción registrada en el período.",9,gris)
    titulo(232,"03 / Pendientes actuales, al día de la consulta")
    saldo=d["cartera_actual"]
    escribir(36,207,"POR RECIBIR DE CLIENTES",7,gris,True); escribir(310,207,"DE ESE SALDO, VENCIDO",7,gris,True)
    escribir(36,185,pesos(saldo["saldo"]),18,verde,True); escribir(310,185,pesos(saldo["saldo_vencido"]),18,verde,True)
    parrafo(36,173,f"{saldo['pendientes']} cobros con saldo. {saldo['vencidos']} vencidos y {saldo['vencen_hoy']} vencen hoy. Estos saldos son actuales, no una reconstrucción del cierre histórico.",ancho-72,8,29)
    principales=d["clientes_con_saldo_actual"][:3]
    if principales: parrafo(36,145,"Mayores saldos actuales: "+" | ".join(f"{f['cliente']}: {pesos(f['saldo_clp'])}" for f in principales),ancho-72,7,22)
    if d["cerrada"]: escribir(36,113,"Saldo actual de pagos cerrados de esta semana: "+pesos(d["saldo_cierres_semana"]),9,verde)
    else: escribir(36,113,"Descargar este resumen no confirma el cierre de pagos.",9,verde)
    parrafo(36,98,"Alcance: producción por fecha de jornada, con ajustes separados; pagos calculados o congelados al cerrar. Los movimientos de dinero usan la fecha registrada del abono. Los cobros estimados no son ingresos recibidos ni utilidad. No se verifican bancos ni se emiten facturas.",ancho-72,7.5,43)
    escribir(36,37,"Agricolix / Documento de gestión interna / Generado desde los registros disponibles",7,gris)
    escribir(ancho-61,37,"1 / 1",7,gris)
    c.showPage(); c.save()
    return salida.getvalue()
