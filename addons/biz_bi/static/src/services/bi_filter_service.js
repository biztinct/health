/** @odoo-module **/

import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";

/**
 * Reactive dashboard filter store. Widgets subscribe by reading the state
 * inside their render/effects; global filters set here re-render them with
 * merged extra_filters. `crossFilter` and `drillPath` are wired in Phase 2 —
 * datapoint clicks already carry dimension keys.
 */
export const biFilterService = {
    start() {
        const state = reactive({
            // filterId -> {op, value} (dashboard global filters)
            globalFilters: {},
            crossFilter: null,
            drillPath: [],
        });

        return {
            state,

            setGlobalFilter(filterId, opValue) {
                if (opValue === null) {
                    delete state.globalFilters[filterId];
                } else {
                    state.globalFilters[filterId] = opValue;
                }
            },

            clearAll() {
                state.globalFilters = {};
                state.crossFilter = null;
                state.drillPath = [];
            },

            /**
             * Compile active global filters into engine extra_filters for one
             * dataset, using the dashboard filter mappings.
             */
            extraFiltersFor(datasetId, filterDefs) {
                const extra = [];
                for (const def of filterDefs) {
                    const active = state.globalFilters[def.id];
                    if (!active || active.value === undefined || active.value === null || active.value === "") {
                        continue;
                    }
                    const mapping = def.mappings.find((m) => m.dataset_id === datasetId);
                    if (mapping) {
                        extra.push({
                            field_id: mapping.field_id,
                            op: active.op,
                            value: active.value,
                        });
                    }
                }
                return extra;
            },
        };
    },
};

registry.category("services").add("bi_filter", biFilterService);
