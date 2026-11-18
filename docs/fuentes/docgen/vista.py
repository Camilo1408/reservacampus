"""Renderiza páginas de un PDF a PNG para revisarlas: python vista.py archivo.pdf 1 2 5"""
import sys
from pathlib import Path
import fitz

pdf = Path(sys.argv[1])
salida = Path(__file__).parent / "_vista"
salida.mkdir(exist_ok=True)
doc = fitz.open(pdf)
for n in (map(int, sys.argv[2:]) if len(sys.argv) > 2 else range(1, doc.page_count + 1)):
    pix = doc[n - 1].get_pixmap(dpi=70)
    destino = salida / f"{pdf.stem[:12]}_p{n:02d}.png"
    pix.save(destino)
    print(destino)
