/**
 * Patch de la Interaction `SurveyResult` (survey/static/src/interactions/
 * survey_result.js) para anadir handlers de filtro de fecha al dropdown
 * inyectado por la vista heredada.
 *
 * Patron URL-driven (identico al nativo, recon punto B/G):
 *   - Cada click setea `date_from` / `date_to` en URLSearchParams y hace
 *     redirect(window.location.pathname + "?" + params.toString()).
 *   - El controller (override de _get_results_page_user_input_domain) anade
 *     los Domain(create_date, ...) al dominio base.
 *   - El DOM resultante ya esta filtrado server-side -> window.print()
 *     (handler nativo onPrintResultsClick, NO se toca) imprime lo filtrado.
 *
 * Extender dynamicContent en setup() patcheado: colibri.js:31 llama setup()
 * ANTES de leer dynamicContent (linea 57). Confirmado por inspeccion.
 *
 * onClearFiltersClick: patcheamos para borrar tambien date_from/date_to;
 * llamamos super() despues para que el nativo borre filters/finished/etc.
 * y redirija.
 */
import { patch } from "@web/core/utils/patch";
import { redirect } from "@web/core/utils/urls";
import { SurveyResult } from "@survey/interactions/survey_result";

// Formato YYYY-MM-DD usando los getters LOCALES (no UTC) para evitar
// drift de un dia en zonas horarias al oeste (Peru, etc.).
function toISODate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}

patch(SurveyResult.prototype, {
    setup() {
        super.setup(...arguments);

        // Anadir handlers de los selectores BIOCRETO al dynamicContent.
        // Object.assign no destruye los handlers nativos (mismo nivel de
        // claves), solo anade los nuestros.
        Object.assign(this.dynamicContent, {
            ".o_bc_filter_date_today": {
                "t-on-click": (ev) => {
                    ev.preventDefault();
                    this.biocretoApplyShortcut("today");
                },
            },
            ".o_bc_filter_date_week": {
                "t-on-click": (ev) => {
                    ev.preventDefault();
                    this.biocretoApplyShortcut("week");
                },
            },
            ".o_bc_filter_date_month": {
                "t-on-click": (ev) => {
                    ev.preventDefault();
                    this.biocretoApplyShortcut("month");
                },
            },
            ".o_bc_filter_date_year": {
                "t-on-click": (ev) => {
                    ev.preventDefault();
                    this.biocretoApplyShortcut("year");
                },
            },
            ".o_bc_filter_date_apply": {
                "t-on-click": (ev) => {
                    ev.preventDefault();
                    this.biocretoApplyManual();
                },
            },
        });
    },

    /**
     * Calcula el rango [desde, hasta] para cada atajo. Todos cierran en HOY
     * (el controller extiende dt_to al fin del dia, asi que "hasta hoy" =
     * incluye registros creados en lo que va del dia actual).
     */
    biocretoComputeRange(kind) {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        let from;
        if (kind === "today") {
            from = today;
        } else if (kind === "week") {
            // Lunes = 1 (ISO). JS Date.getDay(): domingo=0, lunes=1, ..., sabado=6.
            const dow = now.getDay();
            const diff = dow === 0 ? 6 : dow - 1;
            from = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diff);
        } else if (kind === "month") {
            from = new Date(now.getFullYear(), now.getMonth(), 1);
        } else if (kind === "year") {
            from = new Date(now.getFullYear(), 0, 1);
        }
        return { from: toISODate(from), to: toISODate(today) };
    },

    biocretoApplyShortcut(kind) {
        const { from, to } = this.biocretoComputeRange(kind);
        this.biocretoRedirectWithDates(from, to);
    },

    biocretoApplyManual() {
        // Los <input> estan dentro del <li class="o_biocreto_date_filter">
        // que es hijo del root `.o_survey_result` (this.el).
        const fromEl = this.el.querySelector(".o_bc_date_from");
        const toEl = this.el.querySelector(".o_bc_date_to");
        this.biocretoRedirectWithDates(fromEl?.value || "", toEl?.value || "");
    },

    biocretoRedirectWithDates(from, to) {
        const params = new URLSearchParams(window.location.search);
        if (from) {
            params.set("date_from", from);
        } else {
            params.delete("date_from");
        }
        if (to) {
            params.set("date_to", to);
        } else {
            params.delete("date_to");
        }
        redirect(window.location.pathname + "?" + params.toString());
    },

    /**
     * Patch para "Remove all filters": borrar tambien date_from/date_to
     * antes de delegar al super (que borrara filters/finished/failed/passed
     * y redirigira con el querystring resultante).
     */
    onClearFiltersClick() {
        const params = new URLSearchParams(window.location.search);
        params.delete("date_from");
        params.delete("date_to");
        // Reescribir history.state SIN navegar, para que el super lea ya
        // limpio. Patron: actualizar URL local + delegar.
        const newSearch = params.toString();
        const newUrl = window.location.pathname + (newSearch ? "?" + newSearch : "");
        window.history.replaceState(window.history.state, "", newUrl);
        return super.onClearFiltersClick(...arguments);
    },
});
