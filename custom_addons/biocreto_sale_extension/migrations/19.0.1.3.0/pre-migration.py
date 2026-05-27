def migrate(cr, version):
    """Pre-migración v1.2.0 → v1.3.0.

    Los campos biocreto_estructura / biocreto_tipo_cemento / biocreto_huso_tmn
    pasan de Selection (VARCHAR en BD) a Many2one (INTEGER FK). PostgreSQL no
    castea implícitamente VARCHAR → INTEGER, así que el ALTER COLUMN que Odoo
    intentaría falla con 'cannot cast type character varying to integer'.

    Se aceptó la pérdida de los valores anteriores (datos de prueba). Esta
    pre-migración elimina las columnas viejas para que Odoo las recree con
    el tipo correcto durante el update normal del módulo.
    """
    cr.execute("""
        ALTER TABLE sale_order_line
            DROP COLUMN IF EXISTS biocreto_estructura,
            DROP COLUMN IF EXISTS biocreto_tipo_cemento,
            DROP COLUMN IF EXISTS biocreto_huso_tmn
    """)
