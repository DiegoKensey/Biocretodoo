/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarCommonPopover } from "@web/views/calendar/calendar_common/calendar_common_popover";

/**
 * Patch del popover del calendario para agregar el botón "Ir a"
 * (Google Maps Directions) en el footer, entre "Editar/Vista" y el tacho.
 *
 * Componente verificado en v19:
 *   odoo/addons/web/static/src/views/calendar/calendar_common/calendar_common_popover.js:12-18
 *     export class CalendarCommonPopover extends Component {
 *         static template = "web.CalendarCommonPopover";
 *         static subTemplates = {
 *             popover: "web.CalendarCommonPopover.popover",
 *             body:    "web.CalendarCommonPopover.body",
 *             footer:  "web.CalendarCommonPopover.footer",   <-- heredamos este
 *         };
 *     }
 *
 * El record del evento expone props.record.rawRecord (verificado en
 * calendar_common_popover.xml:48, donde el componente Record interno
 * recibe values="props.record.rawRecord"). De ahí leemos
 * biocreto_gmaps_url (que viene en el rawRecord porque está declarado
 * como field del <calendar> en sale_order_calendar_views.xml).
 */
patch(CalendarCommonPopover.prototype, {
    get biocretoGmapsUrl() {
        const rec = this.props.record?.rawRecord;
        return rec ? rec.biocreto_gmaps_url || false : false;
    },
    biocretoOpenGmaps() {
        const url = this.biocretoGmapsUrl;
        if (url) {
            window.open(url, "_blank", "noopener,noreferrer");
        }
    },
});
