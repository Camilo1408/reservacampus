"""Word reduce las imágenes a ~200 ppi al exportar a PDF y se pixelan al hacer zoom.
Este script reemplaza cada imagen del PDF por su PNG original (docs/img) en resolución completa.
Uso: python pdf_alta_resolucion.py [archivo.pdf ...]   (por defecto, todos los de docs/entregables)
"""
import sys
from pathlib import Path

import fitz

RAIZ = Path(__file__).resolve().parents[3]
IMG = RAIZ / "docs" / "img"


def huella(pix):
    """Miniatura de 16x16 en gris para comparar imágenes."""
    if pix.n - pix.alpha != 1:
        pix = fitz.Pixmap(fitz.csGRAY, pix)
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    peq = fitz.Pixmap(pix, 16, 16, None)
    return peq.samples


def indice():
    out = []
    for f in IMG.rglob("*.png"):
        pix = fitz.Pixmap(str(f))
        out.append((f, pix.width / pix.height, huella(pix), pix.width))
    return out


def distancia(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def procesar(pdf, fuentes):
    doc = fitz.open(pdf)
    hechos, vistos = 0, {}
    for pg in doc:
        for im in pg.get_images(full=True):
            xref = im[0]
            if xref in vistos:
                continue
            base = fitz.Pixmap(doc, xref)
            if base.width < 200:
                vistos[xref] = None
                continue
            asp, h = base.width / base.height, huella(base)
            cand = [(distancia(h, hf), f, w) for f, a, hf, w in fuentes if abs(a - asp) / asp < 0.02]
            if not cand:
                vistos[xref] = None
                continue
            d, f, w = min(cand)
            if d < 12 and w > base.width:
                pg.replace_image(xref, filename=str(f))
                hechos += 1
            vistos[xref] = f
    doc.save(str(pdf) + ".tmp", garbage=3, deflate=True)
    doc.close()
    Path(str(pdf) + ".tmp").replace(pdf)
    print(f"{Path(pdf).name}: {hechos} imágenes en alta resolución")


if __name__ == "__main__":
    fuentes = indice()
    pdfs = sys.argv[1:] or [str(p) for p in (RAIZ / "docs" / "entregables").glob("0*.pdf") if not p.name.startswith("07_")]
    for p in pdfs:
        procesar(p, fuentes)
