import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

// Copiado de approvals/static/src/views/kanban/approvals_category_kanban_controller.js
export class RequerimientoCategoriaKanbanController extends KanbanController {
    async setup() {
        super.setup();
        this.action = useService("action");
    }

    OpenNewRequerimiento() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "biocreto.requerimiento",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export class RequerimientoCategoriaKanbanRenderer extends KanbanRenderer {
    async archiveRecord(record, active) {
        if (active) {
            this.dialog.add(ConfirmationDialog, {
                body: _t("¿Seguro que desea archivar este registro?"),
                confirmLabel: _t("Archivar"),
                confirm: () => {
                    record.archive();
                    this.props.list.load();
                },
                cancel: () => {},
            });
        } else {
            record.unarchive();
            this.props.list.load();
        }
    }
}
