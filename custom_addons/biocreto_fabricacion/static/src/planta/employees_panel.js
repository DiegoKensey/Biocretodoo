/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Panel lateral de operadores. Reusa metodos de hr.employee expuestos por mrp_workorder:
 *   get_all_employees, login, logout.
 * PIN opcional: si el empleado no tiene PIN, login(pin=False) pasa directo
 * (verificado en V6: signature hr.employee.login(pin=False, set_in_session=True)).
 */
export class PlantaEmployeesPanel extends Component {
    static template = "biocreto_fabricacion.EmployeesPanel";
    static props = {
        onClose: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            all: [],
            connected: [],
            adminId: null,
            loading: false,
        });

        onWillStart(async () => await this.reload());
    }

    async reload() {
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "hr.employee", "get_all_employees", [null, null],
            );
            // v19: get_all_employees devuelve {all: [...], connected: [...], admin: {...}}
            this.state.all = result?.all || [];
            this.state.connected = (result?.connected || []).map(e => e.id);
            this.state.adminId = result?.admin?.id || null;
        } catch (err) {
            this.notification.add(_t("No se pudo cargar operadores"),
                                  { type: "warning" });
        } finally {
            this.state.loading = false;
        }
    }

    isConnected(employeeId) {
        return this.state.connected.includes(employeeId);
    }

    async toggleConnect(employee) {
        this.state.loading = true;
        try {
            if (this.isConnected(employee.id)) {
                await this.orm.call("hr.employee", "logout",
                                    [employee.id, false, true]);
            } else {
                await this.orm.call("hr.employee", "login",
                                    [employee.id, false, true]);
            }
            await this.reload();
        } catch (err) {
            this.notification.add(
                _t("No se pudo conectar/desconectar operador"),
                { type: "warning" },
            );
        } finally {
            this.state.loading = false;
        }
    }
}
