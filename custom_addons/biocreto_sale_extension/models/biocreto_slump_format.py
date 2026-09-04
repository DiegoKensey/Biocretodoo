"""Formato ÚNICO del slump para todo el sistema BIOCRETO.

Este módulo existe SOLO para alojar `biocreto_format_slump`. Es
deliberadamente una función suelta y no un método de modelo: la consumen
la línea de venta (compute de `biocreto_slump_rango`) y, a través del
campo relacionado, los reportes. Una sola implementación es lo que hace
imposible que dos partes del sistema impriman un slump de forma distinta.

v19.0.1.9.0: antes vivía en `biocreto_slump_rango.py`, junto al catálogo
`biocreto.slump.rango`. Ese catálogo se eliminó (el slump de bombeo pasó
a ser una referencia a la línea de concreto de la propia cotización), así
que el helper se mudó a un archivo propio.
"""

# ═════════════════════════════════════════════════════════════════════
# Tolerancia para comparar dos slumps.
#
# Los campos son Float con digits=(16, 2): la unidad significativa es la
# centésima de pulgada. 0.001 queda un orden por debajo — distingue 6.00
# de 6.01 y absorbe el ruido binario del float.
#
# ★ NUNCA comparar dos slumps con `==`. En base los valores llegan como
# numeric 6.00 y el float que reconstruye psycopg puede no ser idéntico
# bit a bit al 6.0 literal de Python. Un `==` fallaría de forma silenciosa
# e intermitente y una factura ya emitida pasaría a imprimir `6" - 6"` al
# reimprimirse, que es exactamente lo que hay que evitar.
# ═════════════════════════════════════════════════════════════════════
BIOCRETO_SLUMP_TOL = 0.001


def biocreto_format_slump(minimo, maximo):
    """Devuelve la etiqueta imprimible de un rango de slump.

        (6, 6)      -> '6"'
        (6.00, 6.0) -> '6"'            <- comparación con tolerancia
        (7, 8)      -> '7" - 8"'
        (6.5, 7.5)  -> '6.5" - 7.5"'
        (0, 0)      -> ''              <- nunca '0"' ni False
        (6, 0)      -> ''              <- falta un extremo: no se inventa

    El `%g` es la convención que ya usaba el proyecto para imprimir el
    slump: suprime los decimales cuando el valor es entero (6, no 6.00) y
    los conserva cuando los tiene (6.5).
    """
    if not minimo or not maximo:
        return ''
    if abs(minimo - maximo) < BIOCRETO_SLUMP_TOL:
        return '%g"' % minimo
    return '%g" - %g"' % (minimo, maximo)
