import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Da el nivel base (Solicitante) a todo el personal interno ya existente
    y a los usuarios que se creen en adelante.

    El ACL del modulo NO cuelga de base.group_user (a diferencia del nativo
    approvals, ver security/ir.model.access.csv), de modo que sin este hook el
    nivel "No" dejaria a toda la plantilla sin acceso al modulo.

    Dos efectos:
      1. Usuarios internos activos existentes -> se les anade el grupo.
      2. base.default_user_group -> se le anade el grupo en implied_ids, que es
         el mecanismo v19 para los usuarios nuevos
         (odoo/addons/base/models/res_users.py:203-212 `_default_groups`).
         NOTA: en v19 NO existe `base.default_user`; la plantilla de usuario
         nuevo se expresa con `base.default_user_group`.
    """
    solicitante = env.ref(
        'biocreto_requerimientos.group_requerimiento_solicitante',
        raise_if_not_found=False,
    )
    if not solicitante:
        _logger.warning("biocreto_requerimientos: grupo Solicitante no encontrado.")
        return

    # 1) Personal interno ya existente.
    internal_users = env['res.users'].sudo().search([
        ('active', '=', True),
        ('share', '=', False),
        ('group_ids', 'not in', solicitante.ids),
    ])
    if internal_users:
        solicitante.sudo().write({'user_ids': [(4, user.id) for user in internal_users]})
        _logger.info(
            "biocreto_requerimientos: grupo Solicitante asignado a %s usuario(s) interno(s).",
            len(internal_users),
        )

    # 2) Usuarios nuevos.
    default_group = env.ref('base.default_user_group', raise_if_not_found=False)
    if default_group and solicitante not in default_group.implied_ids:
        default_group.sudo().write({'implied_ids': [(4, solicitante.id)]})
        _logger.info(
            "biocreto_requerimientos: grupo Solicitante anadido a base.default_user_group."
        )

    # 3) El administrador del sistema queda como Administrador de
    #    Requerimientos: sin esto nadie podria configurar las categorias del
    #    modulo recien instalado. El nativo approvals hace lo mismo por data
    #    XML (approvals/data/approval_category_data.xml:4-6); aqui se hace en
    #    el hook porque es idempotente y no depende de la semantica de noupdate
    #    sobre un xmlid ajeno (base.user_admin).
    manager = env.ref(
        'biocreto_requerimientos.group_requerimiento_manager', raise_if_not_found=False)
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if manager and admin and manager not in admin.all_group_ids:
        manager.sudo().write({'user_ids': [(4, admin.id)]})
        _logger.info(
            "biocreto_requerimientos: grupo Administrador asignado a base.user_admin."
        )
