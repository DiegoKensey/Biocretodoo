import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";

import {
    RequerimientoCategoriaKanbanRenderer,
    RequerimientoCategoriaKanbanController,
} from "./requerimiento_categoria_kanban_controller";

export const requerimientoCategoriaKanbanView = {
    ...kanbanView,
    Controller: RequerimientoCategoriaKanbanController,
    Renderer: RequerimientoCategoriaKanbanRenderer,
    buttonTemplate: "biocreto_requerimientos.RequerimientoCategoriaKanbanView.Buttons",
};

registry
    .category("views")
    .add("biocreto_requerimiento_categoria_kanban", requerimientoCategoriaKanbanView);
