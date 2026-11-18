"""Apoyo de la importación inteligente: reconocimiento de nombres de trabajadores.

Funciones puras (sin base de datos) para que se puedan probar fácilmente.
"""

from difflib import SequenceMatcher
import re
import unicodedata

UMBRAL_PARECIDO = 0.85


def clave_nombre(valor: str) -> str:
    """Nombre comparable: sin tildes, en minúscula, sin espacios de más y sin
    lo que va entre paréntesis (en las planillas indica quién trajo al trabajador)."""
    sin_parentesis = re.sub(r"\([^)]*\)", " ", valor or "")
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", sin_parentesis)
        if not unicodedata.combining(c)
    )
    return " ".join(sin_tildes.casefold().split())


def partir_nombre(valor: str):
    """'Manuel Vasquez (Ferddy)' -> ('Manuel', 'Vasquez'). Sin apellido queda vacío."""
    limpio = " ".join(re.sub(r"\([^)]*\)", " ", valor or "").split())
    partes = limpio.split(" ", 1)
    return partes[0], (partes[1] if len(partes) > 1 else "")


def son_parecidos(a: str, b: str) -> bool:
    """True si dos nombres distintos podrían ser la misma persona
    (error de tipeo o nombre incompleto)."""
    ca, cb = clave_nombre(a), clave_nombre(b)
    if not ca or not cb or ca == cb:
        return False
    ta, tb = ca.split(), cb.split()
    # Primeros nombres distintos (Raul / Samuel Balceras) son personas distintas.
    if SequenceMatcher(None, ta[0], tb[0]).ratio() < 0.8:
        return False
    if SequenceMatcher(None, ca, cb).ratio() >= UMBRAL_PARECIDO:
        return True
    largo = min(len(ta), len(tb))
    # Mismo primer nombre y el resto parecido o incompleto (Marcial / Marcial Costana).
    if ta[0] == tb[0] and (largo == 1 or
            SequenceMatcher(None, " ".join(ta[:largo]), " ".join(tb[:largo])).ratio() >= UMBRAL_PARECIDO):
        return True
    return False


def analizar_trabajadores(nombres_excel: dict, trabajadores_bd: list, alias: dict):
    """Clasifica cada nombre de las planillas.

    nombres_excel: {nombre: cantidad de registros}
    trabajadores_bd: [(id, nombre, apellido, estado)]
    alias: {clave de nombre: id_trabajador}
    Devuelve una lista de dicts con estado:
      'reconocido' -> ya existe (o tiene equivalencia guardada), no hay que hacer nada
      'pregunta'   -> se parece a otro; hay que preguntar si es la misma persona
      'nuevo'      -> no existe ni se parece a nada; se creará
    """
    por_clave = {}
    for id_, nombre, apellido, estado in trabajadores_bd:
        por_clave.setdefault(clave_nombre(f"{nombre} {apellido}"), []).append((id_, estado))
    ficha = {id_: f"{nombre} {apellido}".strip() for id_, nombre, apellido, _ in trabajadores_bd}

    # Un mismo nombre escrito igual en distintas formas (tildes, paréntesis) cuenta una vez.
    grupos = {}
    for nombre, cantidad in nombres_excel.items():
        g = grupos.setdefault(clave_nombre(nombre), {"nombre": nombre, "cantidad": 0, "variantes": []})
        g["cantidad"] += cantidad
        g["variantes"].append(nombre)
        if cantidad > nombres_excel[g["nombre"]]:
            g["nombre"] = nombre

    resultado = []
    pendientes = []
    for clave, g in grupos.items():
        id_exacto = por_clave.get(clave, [])
        if len(id_exacto) == 1:
            resultado.append({**g, "estado": "reconocido", "id_trabajador": id_exacto[0][0],
                              "coincide_con": ficha[id_exacto[0][0]], "candidatos": []})
        elif clave in alias and alias[clave] in ficha:
            resultado.append({**g, "estado": "reconocido", "id_trabajador": alias[clave],
                              "coincide_con": ficha[alias[clave]], "candidatos": []})
        else:
            pendientes.append((clave, g))

    for clave, g in pendientes:
        candidatos = [
            {"tipo": "base", "id_trabajador": id_, "nombre": nombre_bd}
            for id_, nombre_bd in ficha.items() if son_parecidos(g["nombre"], nombre_bd)
        ]
        # Otros nombres de las planillas: se pregunta una sola vez por pareja,
        # en el nombre con menos registros (el más usado queda como referencia).
        for otra_clave, otro in pendientes:
            if otra_clave != clave and son_parecidos(g["nombre"], otro["nombre"]):
                menor = (g["cantidad"], g["nombre"]) < (otro["cantidad"], otro["nombre"])
                if menor:
                    candidatos.append({"tipo": "planilla", "nombre": otro["nombre"]})
        resultado.append({**g, "estado": "pregunta" if candidatos else "nuevo",
                          "id_trabajador": None, "coincide_con": None, "candidatos": candidatos})

    resultado.sort(key=lambda r: (r["estado"] != "pregunta", r["nombre"].casefold()))
    return resultado


def resolver_trabajador(nombre_excel: str, por_clave: dict, alias: dict, decisiones: dict):
    """Decide a qué trabajador corresponde un nombre de planilla.

    decisiones: {clave de nombre: {'id_trabajador': int} | {'igual_a': nombre} | {'crear': True}}
    Devuelve ('id', id) | ('crear', clave) | None.
    Prioridad: decisión de quien importa, luego nombre exacto, luego equivalencia guardada.
    """
    clave = clave_nombre(nombre_excel)
    for _ in range(10):  # sigue cadenas "igual a" con tope para evitar ciclos
        decision = decisiones.get(clave)
        if not decision:
            break
        if decision.get("id_trabajador"):
            return ("id", decision["id_trabajador"])
        if decision.get("igual_a"):
            clave = clave_nombre(decision["igual_a"])
            continue
        if decision.get("crear"):
            return ("crear", clave)
        break
    exactos = por_clave.get(clave, [])
    if len(exactos) == 1:
        return ("id", exactos[0])
    if len(exactos) > 1:
        return None
    if clave in alias:
        return ("id", alias[clave])
    return None
