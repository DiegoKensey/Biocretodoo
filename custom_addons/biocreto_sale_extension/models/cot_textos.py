# -*- coding: utf-8 -*-
"""Fuente unica de los seis textos base de los reportes de cotizacion.

POR QUE ESTE MODULO EXISTE
==========================
El mismo texto lo necesitan tres consumidores:

  1. el `default` de cada campo Html de `res.company` -> companias NUEVAS
     (models/res_company.py)
  2. el sembrado de las companias que YA existen -> `-i` via hooks.py y
     `-u` via el <function> de data/biocreto_cot_textos.xml
  3. el respaldo del QWeb, en el `t-else` de cada bloque
     (biocreto_sale_report_cotizacion/report/report_cotizacion.xml)

Tenerlo escrito tres veces era garantia de que se desincronizaran. Los
tres leen de aqui: los dos primeros importando el diccionario, y el QWeb
llamando a `res.company._biocreto_cot_texto_base(campo)`, que devuelve
Markup para que `t-out` no lo escape.

DE DONDE SALE EL CONTENIDO
==========================
Extraido programaticamente de los `t-else` del QWeb con lxml, no
transcrito a mano: el requisito era que coincidiera caracter a caracter
con lo que el reporte imprimia antes de que estos campos existieran.

EL <ul> ENVOLVENTE
==================
Cada valor va envuelto en <ul>...</ul>, no como <li> sueltos, porque esa
es exactamente la estructura que produce el editor de texto enriquecido
al guardar una lista de vinetas. Si el `default` guardara <li> sueltos,
el campo se veria distinto al abrirlo para editar que al sembrarlo, y el
usuario perderia la lista en cuanto tocara el editor.

Ese <ul> queda ANIDADO dentro del <ul> que el QWeb ya pone. Las cuatro
tarjetas del grid lo absorben sin ruido porque su regla SCSS
(`.biocreto-cot .info-card ul`) es descendiente y alcanza al anidado. La
banda de Capacidad Operativa necesito una regla propia
(`.biocreto-cot .capacidad-list ul`), porque la suya cuelga de la clase
concreta y dejaba al <ul> anidado con su vineta nativa encima de la
nuestra.

QUE NO ESTA AQUI
================
Ni el titulo de cada bloque, ni la forma de pago, ni la vigencia. El
titulo es fijo en el QWeb; los otros dos se calculan de la orden (del
termino de pago y de validity_date) y se imprimen como vinetas propias
alrededor de este cuerpo.
"""

TEXTOS_COT = {
    # biocreto_cot_menor_condiciones  (2 items)
    # v19.0.1.13.0: se quito la vineta "Los precios incluyen IGV
    # (18%) y son validos exclusivamente para el volumen y
    # resistencia indicados." a peticion del usuario, que ya la
    # habia borrado a mano del campo de la compania Biocreto.
    #
    # Aqui solo cambia el texto BASE, o sea lo que reciben las
    # companias NUEVAS y lo que imprime el `t-else` del QWeb si el
    # campo esta vacio. El contenido ya guardado NO se toca: el
    # sembrado escribe unicamente donde is_html_empty dice que el
    # campo esta vacio (res_company._biocreto_cot_sembrar_textos).
    'biocreto_cot_menor_condiciones':
        '<ul>'
        '<li>La programación del despacho requiere confirmación con al menos <b>48 horas</b> de anticipación.</li>'
        '<li>Las condiciones de aceptación de probetas se rigen por la NTP 339.033, NTP 339.034 y NTP 339.036.</li>'
        '</ul>',

    # biocreto_cot_mayor_info_complementaria  (3 items)
    'biocreto_cot_mayor_info_complementaria':
        '<ul>'
        '<li>Tiempo de espera en obra: 10 a 20 minutos</li>'
        '<li>Volumen mínimo de suministro: 5 m³</li>'
        '<li>Atenciones bajo el volumen mínimo aplican flete de transporte por viaje</li>'
        '</ul>',

    # biocreto_cot_mayor_terminos  (3 items)
    'biocreto_cot_mayor_terminos':
        '<ul>'
        '<li>Anticipación: 72 horas con pre-programación semanal</li>'
        '<li>Flete adicional: atenciones ≤ 5 m³ con cargo extra por viaje</li>'
        '<li>Disponibilidad: lunes a sábado · nocturno y feriados con recargo</li>'
        '</ul>',

    # biocreto_cot_mayor_especificaciones  (6 items)
    'biocreto_cot_mayor_especificaciones':
        '<ul>'
        '<li>Cemento: Portland ASTM C-150 Tipo I — Andino</li>'
        '<li>Agua: cumple ASTM C-1602 para concreto</li>'
        '<li>Arena gruesa: Río Mantaro (Matahuasi) y cantera Orcotuna</li>'
        '<li>Piedra chancada: Río Mantaro, Matahuasi</li>'
        '<li>Aditivos: Fluxcrete 1000, Fluxcrete 31RF, Plastcon RF20</li>'
        '<li>Norma: NTP 339.114 y RNE 0.60 Concreto Armado</li>'
        '</ul>',

    # biocreto_cot_mayor_servicios  (5 items)
    'biocreto_cot_mayor_servicios':
        '<ul>'
        '<li>Máquina vibradora para compactado (opcional)</li>'
        '<li>Probetas NTP 339.114 — 3 testigos cada 40 m³</li>'
        '<li>Prueba de SLUMP en obra</li>'
        '<li>Rotura a 28 días + certificación de probetas</li>'
        '<li>Asesoría técnica en obra</li>'
        '</ul>',

    # biocreto_cot_mayor_capacidad  (7 items)
    'biocreto_cot_mayor_capacidad':
        '<ul>'
        '<li>03 plantas semiautomatizadas — Cajas, Concepción, Comuneros</li>'
        '<li>03 plantas móviles para obra</li>'
        '<li>12 camiones mixer de concreto</li>'
        '<li>03 bombas telescópicas — 32 m, 38 m, 47 m</li>'
        '<li>02 volquetes · 03 cargadores frontales · 01 retroexcavadora</li>'
        '<li>50 m³/hora de capacidad (sede Cajas)</li>'
        '<li>Laboratorio equipado · staff técnico especializado</li>'
        '</ul>',
}
