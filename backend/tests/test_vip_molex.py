import io

import pytest
from openpyxl import Workbook

from app.dominio import materiales as mat
from app.dominio.vip import ClienteVip, leer_archivo_vip


def _xlsx(hojas: dict[str, list[list]]) -> bytes:
    libro = Workbook()
    libro.remove(libro.active)
    for nombre, filas in hojas.items():
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_lee_vip_de_excel_en_la_hoja_que_tenga_cliente():
    contenido = _xlsx({
        "Portada": [["Lista de clientes VIP 2026"]],
        "Datos": [
            ["Cliente", "Razon Social", "Clase Cliente", "Correo", "Telefono"],
            [200100.0, "Hotel Palmira", "Corporativo", "gerencia@hotel.hn", "9999-0000"],
            ["200101", "  Banco Centro ", "Gobierno", None, None],
            [200100, "Repetido", "", None, None],
            ["N/D", "Sin código", "", None, None],
        ],
    })
    assert leer_archivo_vip(contenido, "VIP.xlsx") == [
        ClienteVip("200100", "Hotel Palmira", "Corporativo"),
        ClienteVip("200101", "Banco Centro", "Gobierno"),
    ]


def test_lee_vip_de_csv_en_latin1():
    contenido = "CLIENTE,NOMBRE,CLASE\n300.0,Ferretería López,A\n301,,\n".encode("latin-1")
    assert leer_archivo_vip(contenido, "vip.csv") == [ClienteVip("300", "Ferretería López", "A"), ClienteVip("301")]


def test_vip_sin_columna_cliente_o_formato_viejo():
    with pytest.raises(ValueError, match="CLIENTE"):
        leer_archivo_vip(b"CODIGO,NOMBRE\n1,a\n", "vip.csv")
    with pytest.raises(ValueError, match=".xlsx"):
        leer_archivo_vip(b"...", "vip.xls")


@pytest.mark.parametrize(("comentario", "esperado"), [
    ("Se le añadió una molex en medio del tramo y se fusionó", mat.COMENTARIO_NUEVA),
    ("se puso una molex temporal mientras se cambia la acometida", mat.COMENTARIO_NUEVA),
    ("Fibra dañada en la molex, se preparó y se fusiona", mat.COMENTARIO_EXISTENTE),
    ("Se eliminó la molex que ya estaba", mat.COMENTARIO_EXISTENTE),
    ("Se dejó molex en la casa ya que no se encontró la que tenían", mat.COMENTARIO_REEMPLAZO_CASA),
    ("Revisión, molex ok", mat.COMENTARIO_AMBIGUO),
    ("Se cambió un tramo de 40 m", mat.COMENTARIO_EMPALME),
    ("Se cambió conector", mat.COMENTARIO_NADA),
    (None, mat.COMENTARIO_NADA),
])
def test_clasificar_comentario_molex(comentario, esperado):
    assert mat.clasificar_comentario_molex(comentario)[0] == esperado


def test_clasificar_lee_la_enie_danada_de_cepheus_y_recorta_la_frase():
    tipo, frase = mat.clasificar_comentario_molex("x" * 200 + " se da¿aron hilos en una molex " + "y" * 200)
    assert tipo == mat.COMENTARIO_EXISTENTE
    assert frase.startswith("…") and frase.endswith("…") and "molex" in frase


def test_veredicto_molex():
    assert mat.veredicto_molex(1, mat.COMENTARIO_NUEVA) == mat.VEREDICTO_CUADRA
    assert mat.veredicto_molex(1, mat.COMENTARIO_EXISTENTE) == mat.VEREDICTO_CONTRADICE
    assert mat.veredicto_molex(2, mat.COMENTARIO_NADA) == mat.VEREDICTO_SIN_RESPALDO
    assert mat.veredicto_molex(0, mat.COMENTARIO_NUEVA) == mat.VEREDICTO_SIN_DEPURAR
    assert mat.veredicto_molex(0, mat.COMENTARIO_AMBIGUO) == mat.VEREDICTO_CUADRA
    assert mat.veredicto_molex(0, mat.COMENTARIO_NADA) is None
