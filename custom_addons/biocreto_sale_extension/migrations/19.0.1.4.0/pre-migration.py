def migrate(cr, version):
    """Pre-migración v1.3.0 → v1.4.0.

    El campo biocreto_direccion_proyecto (Char) desaparece, sustituido por
    una dirección estructurada (state_id / city_id / district_id / street).

    Problema durante el update: la vista de biocreto_sale_contract_state
    (XML id 'view_order_form_biocreto_contract') hereda sale.view_order_form
    y hace xpath sobre biocreto_direccion_proyecto. Cuando este módulo se
    actualiza antes que contract_state, Odoo recompila el arch combinado
    de sale.view_order_form con la versión nueva de extension (sin el
    campo) y la versión vieja de contract_state (con el xpath obsoleto)
    → fallo de validación → rollback del -u.

    Esta pre-migración borra la vista obsoleta de contract_state por XML
    ID antes de que se valide el arch. contract_state la recreará con su
    arch nuevo cuando se procese su propia actualización (que debe correr
    en el MISMO comando -u biocreto_sale_extension,biocreto_sale_contract_state).
    """
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'biocreto_sale_contract_state'
              AND name   = 'view_order_form_biocreto_contract'
              AND model  = 'ir.ui.view'
        )
    """)
