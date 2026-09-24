{
    'name': 'BIOCRETO Requerimientos',
    'version': '19.0.3.0.0',
    'category': 'Supply Chain',
    'summary': 'Requerimientos internos de EPP, herramientas, limpieza y oficina '
               'con flujo Borrador -> Enviado -> En proceso -> Entregado.',
    'description': (
        "Modulo de requerimientos internos BIOCRETO. Cualquier trabajador "
        "(planta, ventas, laboratorio, administracion, logistica) solicita "
        "materiales y logistica los atiende.\n\n"
        "Replica la arquitectura y la UX del modulo nativo Aprobaciones "
        "(tablero kanban de categorias configurables, formulario con campos "
        "activables por categoria, lineas de producto) pero con modelos propios "
        "y SIN cadena de aprobadores.\n\n"
        "Numeracion propia PLANTA-ANIO-CODIGO#### (ej. ECO-2026-SLT0001) con "
        "reinicio anual y correlativo independiente por par (categoria, planta), "
        "mismo patron que biocreto_compras."
    ),
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    # Icono de la ficha del modulo en Aplicaciones. Sin esta clave Odoo busca
    # por convencion static/description/icon.png; _get_icon_image acepta .svg
    # (odoo/addons/base/models/ir_module.py:257).
    'icon': '/biocreto_requerimientos/static/description/icon.svg',
    'depends': [
        'mail',
        'product',
        'uom',
        'biocreto_base',
        # === BIOCRETO CONSOLIDADO v1 — INICIO (bloque reversible) ===
        # `purchase` para generar la SC, `stock` para leer qty_available por
        # almacen. NO se depende de approvals ni approvals_purchase: su logica
        # se copio como referencia, no se hereda.
        'purchase',
        'stock',
        # === BIOCRETO CONSOLIDADO v1 — FIN ===
        # === ENTREGA DE MATERIALES v19.0.1.2.0 — INICIO ===
        # `hr` : hr.employee (quien recibe) y hr.department (que fija la
        #        ubicacion destino). Ya instalado, v19.0.1.1.
        # `biocreto_base` : ya estaba; aporta res.users.biocreto_firma,
        #        la firma de quien entrega que se pinta en la constancia.
        # `biocreto_pdf_engine` : el reporte se suscribe a PlutoPrint
        #        extendiendo _biocreto_usa_plutoprint.
        # `biocreto_sig` : codigo/version/fecha del formato en la
        #        cabecera, via get_control_for_qweb.
        # `stock` ya era dependencia (la trajo el consolidado), asi que
        # el flujo de entrega NO anade ninguna dependencia de inventario.
        'hr',
        'biocreto_pdf_engine',
        'biocreto_sig',
        # === ENTREGA DE MATERIALES v19.0.1.2.0 — FIN ===
    ],
    'data': [
        'security/biocreto_requerimientos_security.xml',
        'security/ir.model.access.csv',

        'data/mail_message_subtype_data.xml',
        # v19.0.1.8.0: registro SIG BC-GL-FR-11 de la constancia de
        # entrega. Va ANTES de las vistas y del reporte porque es un dato
        # de configuracion que la plantilla consulta en tiempo de render;
        # el orden dentro de `data` no crea dependencia real (el QWeb lo
        # busca por codigo_documento en runtime, no por ref), pero deja
        # los datos agrupados arriba, como el resto del modulo.
        'data/documento_control_data.xml',

        'views/product_category_views.xml',
        # v19.0.1.6.0: biocreto_es_activo se mudo de la categoria al
        # producto. Va DESPUES del de categoria por orden de lectura;
        # no hay dependencia entre ambos.
        'views/product_template_views.xml',
        'views/hr_department_views.xml',
        'views/biocreto_requerimiento_linea_views.xml',
        'views/biocreto_requerimiento_categoria_views.xml',
        'views/biocreto_requerimiento_views.xml',
        # === BIOCRETO CONSOLIDADO v1 — INICIO (bloque reversible) ===
        # El ACL del consolidado va en su PROPIO csv, no al final del
        # ir.model.access.csv existente: el cargador de Odoo
        # (odoo/tools/convert.py:750 -> models.py:1178) no admite filas de
        # comentario en un CSV; una fila que empiece por '#' revienta con
        # IndexError. Y el nombre de archivo NO es libre: convert_csv_import
        # deduce el modelo del basename, asi que tiene que llamarse
        # ir.model.access.csv y vivir en su propia carpeta. Aisla mejor que
        # mezclarlo en el CSV existente.
        'security/consolidado/ir.model.access.csv',
        'views/consolidado_views.xml',
        # === BIOCRETO CONSOLIDADO v1 — FIN ===
        # === ENTREGA DE MATERIALES v19.0.1.2.0 — INICIO ===
        'views/biocreto_requerimiento_entrega_views.xml',
        'report/paperformat.xml',
        'report/report_constancia_entrega.xml',
        # === ENTREGA DE MATERIALES v19.0.1.2.0 — FIN ===
        # === INVENTARIO DE ACTIVOS v19.0.2.0.0 — INICIO ===
        # Va ANTES de menus.xml porque este referencia
        # action_biocreto_inventario_conteo, y el cargador de Odoo
        # resuelve los `ref` en el orden de esta lista.
        'views/res_company_views.xml',
        'views/biocreto_inventario_conteo_views.xml',
        'report/report_inventario_activos.xml',
        # === INVENTARIO DE ACTIVOS v19.0.2.0.0 — FIN ===
        'views/menus.xml',

        'data/biocreto_requerimiento_categoria_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biocreto_requerimientos/static/src/**/*.js',
            'biocreto_requerimientos/static/src/**/*.xml',
            # Ruta EXPLICITA, no un glob de *.scss: en esa misma carpeta
            # vive report_constancia_entrega.scss, que pertenece al bundle
            # del reporte y no debe colarse en el backend.
            'biocreto_requerimientos/static/src/scss/entrega_firma.scss',
            # v19.0.2.0.0: fondo permanente de las tres columnas de
            # estado en la lista de lineas del conteo. Ruta explicita
            # por el mismo motivo que la de arriba.
            'biocreto_requerimientos/static/src/scss/inventario_activos.scss',
        ],
        # Bundle del reporte. Va en web.report_assets_common porque es
        # el que biocreto_pdf_engine inlinea en el HTML que entrega a
        # PlutoPrint (_biocreto_pick_bundle, ir_actions_report.py:314-335).
        'web.report_assets_common': [
            'biocreto_requerimientos/static/src/scss/report_constancia_entrega.scss',
            'biocreto_requerimientos/static/src/scss/report_inventario_activos.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'auto_install': False,
}
