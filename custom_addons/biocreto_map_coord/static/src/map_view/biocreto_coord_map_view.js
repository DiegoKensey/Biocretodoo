/** @odoo-module **/

import { registry } from "@web/core/registry";
import { mapView } from "@web_map/map_view/map_view";
import { BiocretoCoordMapModel } from "./biocreto_coord_map_model";

/**
 * Variante del mapView nativo con MapModel sustituido. Renderer,
 * Controller y ArchParser son los nativos → cero cambios al popup
 * (Nombre / Dirección / Cliente / botones Abrir / Ir a) ni a la lista
 * lateral. Patrón verificado en
 *   addons/project_enterprise/static/src/views/project_task_map/project_task_map_view.js:9-17
 *   addons/stock_enterprise/static/src/map_view/map_view.js:1-12
 *
 * Activación: añadir js_class="biocreto_coord_map" al <map> de cualquier
 * vista que use Float propios para las coordenadas.
 */
export const biocretoCoordMapView = {
    ...mapView,
    Model: BiocretoCoordMapModel,
};

registry.category("views").add("biocreto_coord_map", biocretoCoordMapView);
