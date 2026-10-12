from app.dominio.nombres import normalizar_nombre_cruce, resolver_tecnico_por_similitud

CATALOGO = [
    "Sayra Michelle Escobar Garcia",
    "Elvin Josué Martínez",
    "Melvin Antonio Cruz",
    "Josué David Hernández",
    "Josué Manuel Hernández",
    "Norman Daniel Reyes",
    "Daniel Alejandro Mejía",
]


def test_normalizar_quita_acentos_invisibles_y_resuelve_alias():
    assert normalizar_nombre_cruce("  José​  Pérez ") == "JOSE PEREZ"
    assert normalizar_nombre_cruce("Jeremy Modesto Padilla") == "JERMI MODESTO PADILLA"
    assert normalizar_nombre_cruce(None) == ""


def test_coincidencia_exacta_sin_acentos():
    assert resolver_tecnico_por_similitud("elvin josue martinez", CATALOGO) == (
        "Elvin Josué Martínez", "Elvin Josué Martínez")


def test_nombre_incompleto():
    assert resolver_tecnico_por_similitud("Sayra Escobar", CATALOGO)[0] == "Sayra Michelle Escobar Garcia"


def test_ambiguo_no_se_adivina():
    assert resolver_tecnico_por_similitud("Josué Hernández", CATALOGO) == ("Josué Hernández", None)


def test_una_palabra_contra_primer_nombre():
    assert resolver_tecnico_por_similitud("Daniel", CATALOGO)[0] == "Daniel Alejandro Mejía"
    assert resolver_tecnico_por_similitud("Elvin", CATALOGO)[0] == "Elvin Josué Martínez"
    assert resolver_tecnico_por_similitud("Saira", CATALOGO)[0] == "Sayra Michelle Escobar Garcia"


def test_sin_parecido_devuelve_original():
    assert resolver_tecnico_por_similitud("Pedro Picapiedra", CATALOGO) == ("Pedro Picapiedra", None)
