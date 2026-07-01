/**
 * Patch de la Interaction `SurveyPrint`
 * (survey/static/src/interactions/survey_print.js, static selector
 * ".o_survey_print").
 *
 * Nativo: `onPrintUserResultsClick()` hace `window.print()` sobre el
 * DOM actual de la pagina /survey/print.
 *
 * Para encuestas BIOCRETO: redirigimos al PDF PlutoPrint ramificado
 * (mismo `action_report_encuesta` que el menu "Imprimir" del backend).
 * URL: `/report/pdf/<report_name>/<user_input_id>` (patron web/
 * controllers/report.py:24-27). El backend aplica `print_report_name`
 * como Content-Disposition -> filename ya sale ramificado
 * ("Encuesta de Satisfaccion - <OV>.pdf" / "Encuesta de Reclamo -
 * <OV>.pdf").
 *
 * Data-attrs (`data-biocreto-tipo`, `data-biocreto-user-input-id`)
 * los inyecta el template heredado (views/survey_page_print_inherit.xml)
 * SOLO para encuestas BIOCRETO. Si no estan (encuesta nativa), el patch
 * delega al super() y todo sigue igual.
 */
import { patch } from "@web/core/utils/patch";
import { SurveyPrint } from "@survey/interactions/survey_print";

patch(SurveyPrint.prototype, {
    onPrintUserResultsClick(ev) {
        const tipo = this.el?.dataset?.biocretoTipo;
        const uiId = this.el?.dataset?.biocretoUserInputId;
        if (tipo && uiId) {
            if (ev && typeof ev.preventDefault === "function") {
                ev.preventDefault();
            }
            window.location =
                `/report/pdf/biocreto_encuestas_reporte.report_encuesta_document/${uiId}`;
            return;
        }
        return super.onPrintUserResultsClick(...arguments);
    },
});
