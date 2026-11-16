# ==========================================================
# AGRICOLIX - CREACIÓN DEL ÍCONO
# Herramienta de desarrollo: dibuja el ícono (un brote verde) y
# genera agricolix.ico junto a este archivo. Solo hace falta volver
# a ejecutarla si se quiere cambiar el diseño.
# Uso: python crear_icono.py   (requiere Pillow: pip install pillow)
# ==========================================================
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

TAMANO = 1024
VERDE = (47, 107, 58, 255)
VERDE_CLARO = (96, 168, 96, 255)
BLANCO = (255, 255, 255, 255)


def punto_curva(p0, control, p1, t):
    """Punto de una curva de Bézier cuadrática."""
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * control[0] + t ** 2 * p1[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * control[1] + t ** 2 * p1[1]
    return x, y


def hoja(dibujo, base, punta, curvatura, color):
    """Hoja en forma de lente entre dos puntos; 'curvatura' define lo ancha que es."""
    medio = ((base[0] + punta[0]) / 2, (base[1] + punta[1]) / 2)
    dx, dy = punta[0] - base[0], punta[1] - base[1]
    largo = math.hypot(dx, dy)
    normal = (-dy / largo, dx / largo)
    c1 = (medio[0] + normal[0] * curvatura, medio[1] + normal[1] * curvatura)
    c2 = (medio[0] - normal[0] * curvatura, medio[1] - normal[1] * curvatura)
    lado1 = [punto_curva(base, c1, punta, i / 40) for i in range(41)]
    lado2 = [punto_curva(punta, c2, base, i / 40) for i in range(41)]
    dibujo.polygon(lado1 + lado2, fill=color)


def dibujar():
    imagen = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    d = ImageDraw.Draw(imagen)
    d.rounded_rectangle((40, 40, TAMANO - 40, TAMANO - 40), radius=230, fill=VERDE)
    # tallo
    d.line([punto_curva((512, 840), (512, 700), (512, 470), i / 30) for i in range(31)], fill=BLANCO, width=62, joint="curve")
    d.ellipse((512 - 31, 840 - 31, 512 + 31, 840 + 31), fill=BLANCO)
    # hojas
    hoja(d, (512, 640), (230, 380), 150, BLANCO)
    hoja(d, (512, 560), (800, 290), 150, VERDE_CLARO)
    hoja(d, (512, 560), (800, 290), 150, BLANCO)
    hoja(d, (512, 470), (512, 215), 95, BLANCO)
    return imagen


if __name__ == "__main__":
    carpeta = Path(__file__).resolve().parent
    imagen = dibujar()
    imagen.save(carpeta / "agricolix.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if len(sys.argv) > 1:  # vista previa opcional
        imagen.resize((256, 256), Image.LANCZOS).save(sys.argv[1])
    print("Listo:", carpeta / "agricolix.ico")
