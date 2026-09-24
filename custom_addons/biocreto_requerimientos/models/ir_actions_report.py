from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # -----------------------------------------------------------------
    # Suscripcion de la constancia de entrega al motor PlutoPrint.
    #
    # NOTA SOBRE DONDE VIVE ESTE CODIGO
    # ---------------------------------
    # La especificacion pedia registrarlo dentro de
    # `biocreto_pdf_engine/models/ir_actions_report.py`. Se ha hecho aqui
    # en su lugar, y a proposito: el motor documenta explicitamente que
    # su set base va VACIO y que cada modulo de reporte se suscribe
    # extendiendo el hook (biocreto_pdf_engine/models/ir_actions_report.py
    # :17-37, "El motor base NO conoce ningun reporte ... El owner de la
    # decision es el modulo del reporte, no el motor").
    #
    # Meterlo en el motor tendria tres efectos indeseables:
    #   1) el motor pasaria a conocer un reporte concreto, rompiendo su
    #      aislamiento y el patron que ya siguen compras y encuestas;
    #   2) obligaria a `-u biocreto_pdf_engine` cada vez que se toque
    #      esta constancia;
    #   3) si manana se desinstala biocreto_requerimientos, el motor
    #      quedaria apuntando a un report_name inexistente.
    #
    # El efecto funcional es identico: el motor matchea por report_name.
    # -----------------------------------------------------------------
    def _biocreto_usa_plutoprint(self):
        res = super()._biocreto_usa_plutoprint()
        res.add('biocreto_requerimientos.report_constancia_entrega')
        # v19.0.2.0.0 — BC-GL-FR-15. Es el PRIMER reporte apaisado del
        # proyecto: el motor lo resuelve leyendo `orientation` del
        # paperformat (ir_actions_report.py:271-281 del motor), asi que
        # basta con suscribirlo aqui como cualquier otro.
        res.add('biocreto_requerimientos.report_inventario_activos')
        return res
