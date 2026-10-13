"""Libros de Excel (.xlsx) con openpyxl: encabezado con estilo, filtros y anchos legibles."""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

Hoja = tuple[str, Sequence[str], Sequence[Sequence[object]]]

_ENCABEZADO = PatternFill("solid", fgColor="28326A")


def _seguro(valor: object) -> object:
    # Un texto que empiece con = + - @ se ejecutaría como fórmula al abrir el archivo.
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor
    return valor


def libro(hojas: Sequence[Hoja]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for nombre, encabezados, filas in hojas:
        ws = wb.create_sheet(nombre[:31])
        ws.append(list(encabezados))
        for celda in ws[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = _ENCABEZADO
            celda.alignment = Alignment(vertical="center")
        for fila in filas:
            ws.append([_seguro(v) for v in fila])
        for i, titulo in enumerate(encabezados, start=1):
            valores = [len(str(titulo))] + [len(str(f[i - 1])) for f in filas[:500] if f[i - 1] is not None]
            ws.column_dimensions[get_column_letter(i)].width = min(max(valores) + 2, 60)
        for columna in ws.iter_cols(min_row=2):
            for celda in columna:
                if isinstance(celda.value, datetime):
                    celda.number_format = "dd/mm/yyyy hh:mm"
                elif isinstance(celda.value, date):
                    celda.number_format = "dd/mm/yyyy"
        ws.freeze_panes = "A2"
        if filas:
            ws.auto_filter.ref = ws.dimensions
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()
