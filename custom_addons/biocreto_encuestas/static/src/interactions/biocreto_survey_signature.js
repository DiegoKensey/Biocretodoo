/**
 * Patch de SurveyForm Interaction — v19.0.3.1.0 (FIX orden invertido).
 *
 * Bug anterior: cortabamos `super.submitForm` en isFinish para abrir el
 * modal de firma, y luego /biocreto_finalize marcaba `done`. Como las
 * encuestas BIOCRETO usan page_per_section con 1 sola seccion, ese
 * submit final cortado era el unico POST a /survey/submit, asi que las
 * respuestas (user_input_line_ids) NUNCA llegaban al server -> tab
 * "Respuestas" y "Ver resultados" salian vacios.
 *
 * Fix — orden invertido (firma primero, submit nativo despues):
 *   1) Capturamos `_super = super.submitForm.bind(this)` ANTES del
 *      callback async (dentro del callback, super.X no es accesible).
 *   2) Abrimos el SignatureDialog (overlay sobre document.body, no toca
 *      el form -> las opciones marcadas siguen en el DOM intactas).
 *   3) Al confirmar la firma, POST a /biocreto_save_signature que SOLO
 *      escribe los 3 campos de firma (sin _mark_done).
 *   4) Luego `await _super(options)` reanuda el flujo nativo:
 *      /survey/submit -> _save_lines (persiste respuestas) -> _mark_done
 *      (candado pasa porque firma ya escrita) -> nextScreen renderiza
 *      el survey_fill_form_done nativo con transicion fade.
 *
 * No usamos redirect(): el flujo nativo ya hace la transicion.
 *
 * Doble candado server-side: _mark_done sigue bloqueando bypass via
 * devtools si falta firma.
 *
 * UX: flag this._biocretoOpened evita abrir 2 modales si el cliente
 * hace doble-click en "Enviar" antes de firmar.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { SurveyForm } from "@survey/interactions/survey_form";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(SurveyForm.prototype, {
    /**
     * v19.0.3.8.0 — Patch del onSubmit SOLO para encuestas BIOCRETO.
     *
     * El ConfirmationDialog del nativo (survey_form.js:417-425) se monta en
     * document.body sin clase distintiva -> no se podia recolorear via SCSS
     * sin contaminar todos los dialogs del frontend. Aqui interceptamos
     * el caso `finish && !sessionInProgress` para BIOCRETO y replicamos
     * la misma llamada pero anadiendole `confirmClass` con clase BIOCRETO.
     * El SCSS biocreto_survey_dialog.scss usa `:has(.o_biocreto_survey_confirm)`
     * para alcanzar tambien el cancel (que esta hardcoded a btn-secondary
     * en confirmation_dialog.xml:9).
     *
     * Para encuestas no-BIOCRETO o cualquier otro target.value, delega
     * al super -> cero impacto en flujo nativo.
     */
    onSubmit(ev) {
        const tipo = this.formEl?.dataset?.biocretoTipo;
        const targetEl = ev.currentTarget;
        if (
            tipo &&
            targetEl.value === "finish" &&
            !this.options.sessionInProgress
        ) {
            ev.preventDefault();
            this.dialog.add(ConfirmationDialog, {
                title: _t("Submit confirmation"),
                body: _t("Are you sure you want to submit the survey?"),
                confirmLabel: _t("Submit"),
                confirmClass: "btn-primary o_biocreto_survey_confirm",
                confirm: () => {
                    this.waitForTimeout(
                        () => this.submitForm({ isFinish: true }),
                        0
                    );
                },
                cancel: () => {},
            });
            return;
        }
        return super.onSubmit(ev);
    },

    async submitForm(options = {}) {
        // Los data-attrs viven en el <form class="o_survey-fill-form">
        // (this.formEl), no en this.el. Ver recon Fase 3 entregable 3:
        // this.el = <div class="o_survey_form"> outer; this.formEl =
        // <form class="o_survey-fill-form"> donde estan TODOS los
        // data-attrs nativos + los nuestros (biocreto-tipo, biocreto-
        // partner-name).
        const tipo = this.formEl?.dataset?.biocretoTipo;
        if (options.isFinish && tipo && !this._biocretoOpened) {
            // Capturar ref al original ANTES del callback async (en el
            // callback, super.submitForm no es accesible por closure).
            // _super apunta al next en la cadena MRO (= original
            // SurveyForm.submitForm), NO al patched -> sin recursion.
            const _super = super.submitForm.bind(this);
            this._biocretoOpened = true;
            this._biocretoOpenSignatureDialog(options, _super);
            return;
        }
        return super.submitForm(...arguments);
    },

    _biocretoOpenSignatureDialog(options, _super) {
        const partnerName =
            this.formEl?.dataset?.biocretoPartnerName || "";
        this.dialog.add(
            SignatureDialog,
            {
                defaultName: partnerName,
                nameAndSignatureProps: {
                    fontColor: "DarkBlue",
                    signatureType: "signature",
                },
                uploadSignature: async ({ name, signatureImage }) => {
                    const signature = (signatureImage || "").split(",")[1];
                    // Paso 1: guardar SOLO la firma (sin _mark_done).
                    const data = await rpc(
                        `/survey/${this.options.surveyToken}/${this.options.answerToken}/biocreto_save_signature`,
                        { name, signature }
                    );
                    if (!data.success) {
                        const msg =
                            typeof data.error === "string" && data.error
                                ? data.error
                                : _t("Error al guardar la firma.");
                        this.services.notification.add(msg, {
                            type: "danger",
                        });
                        // permitir reintentar
                        this._biocretoOpened = false;
                        return;
                    }
                    // Paso 2: reanudar el flujo NATIVO. Lee FormData del
                    // <form> (DOM intacto), POST a /survey/submit que
                    // hara _save_lines + _mark_done, y nextScreen
                    // renderiza el thank-you nativo con fade.
                    await _super(options);
                },
            },
            {
                // Si el cliente cierra el modal sin firmar (ESC / X /
                // click fuera), permitir reintentar mas tarde sin
                // bloquearlo. La encuesta queda en in_progress.
                onClose: () => {
                    this._biocretoOpened = false;
                },
            }
        );
    },
});
