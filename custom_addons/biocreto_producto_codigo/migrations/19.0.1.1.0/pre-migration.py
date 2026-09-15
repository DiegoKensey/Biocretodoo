# -*- coding: utf-8 -*-
"""Converge las bases que recibieron la 19.0.1.0.0.

QUÉ PASÓ
--------
La 1.0.0 renombraba `Herramientas` a `Herramientas eléctricas / manuales`
y le daba el prefijo `HER`. La 1.1.0 parte esa categoría en dos:
`Herramientas manuales` (`HMA`), que conserva los productos, y
`Herramientas eléctricas` (`HEL`), que nace vacía.

Una base instalada de cero con la 1.1.0 no necesita nada de esto: la
semilla ya renombra `Herramientas` directamente a `Herramientas
manuales`. Este script existe solo para las bases que se quedaron en el
nombre intermedio — en la práctica, la de desarrollo.

POR QUÉ EN `pre-` Y NO EN `post-`
---------------------------------
El orden de Odoo es pre-migration -> carga de datos -> post-migration. La
semilla vive en un <function> de data, así que corre EN MEDIO. Si la
corrección fuese `post-`, la semilla se encontraría el nombre intermedio,
no sabría qué hacer con él y dejaría un WARNING de prefijo sin asignar.
Corrigiendo antes, la semilla ve un mundo coherente.

POR QUÉ SQL DIRECTO Y NO EL ORM
-------------------------------
En una pre-migración el registro TODAVÍA NO tiene los campos del módulo:
las clases Python de este addon no se han fusionado aún en el modelo.
Comprobado a las malas — `categoria.biocreto_prefijo` levantaba
`AttributeError: 'product.category' object has no attribute
'biocreto_prefijo'`. La columna sí existe en la tabla desde la 1.0.0, así
que se escribe por SQL. `product.category.name` tampoco es traducible
(product_category.py:17 lo declara sin `translate=True`), así que no hay
JSONB de traducciones que mantener.

Idempotente: si el nombre intermedio no existe, no hace nada.
"""
import logging

_logger = logging.getLogger(__name__)

NOMBRE_INTERMEDIO = 'Herramientas eléctricas / manuales'
NOMBRE_FINAL = 'Herramientas manuales'
PREFIJO_VIEJO = 'HER'
PREFIJO_NUEVO = 'HMA'


def migrate(cr, version):
    if not version:
        # Instalación limpia: no hay nada que converger.
        return

    cr.execute("SELECT id, biocreto_prefijo FROM product_category "
               "WHERE name = %s", [NOMBRE_INTERMEDIO])
    fila = cr.fetchone()
    if not fila:
        _logger.info(
            "biocreto_producto_codigo: no hay categoría %r que converger.",
            NOMBRE_INTERMEDIO)
        return
    categoria_id, prefijo = fila

    cr.execute("SELECT id FROM product_category WHERE name = %s",
               [NOMBRE_FINAL])
    if cr.fetchone():
        _logger.warning(
            "biocreto_producto_codigo: ya existe %r además de %r; se deja "
            "todo como está para no fusionar categorías por cuenta propia.",
            NOMBRE_FINAL, NOMBRE_INTERMEDIO)
        return

    cr.execute("UPDATE product_category SET name = %s WHERE id = %s",
               [NOMBRE_FINAL, categoria_id])
    _logger.info(
        "biocreto_producto_codigo: categoría id=%s renombrada de %r a %r.",
        categoria_id, NOMBRE_INTERMEDIO, NOMBRE_FINAL)

    if prefijo == PREFIJO_VIEJO:
        cr.execute(
            "UPDATE product_category SET biocreto_prefijo = %s WHERE id = %s",
            [PREFIJO_NUEVO, categoria_id])
        _logger.info(
            "biocreto_producto_codigo: prefijo de la categoría id=%s "
            "cambiado de %r a %r. Ningún producto usaba la serie "
            "%s001-%s999, así que no hay códigos que rehacer.",
            categoria_id, PREFIJO_VIEJO, PREFIJO_NUEVO,
            PREFIJO_VIEJO, PREFIJO_VIEJO)
