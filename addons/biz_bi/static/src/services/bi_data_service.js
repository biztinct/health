/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * Data access for all BI surfaces:
 * - batched /bi/query with per-tab result cache and in-flight deduplication
 * - dataset metadata loading
 */
export const biDataService = {
    start() {
        const cache = new Map(); // requestKey -> envelope
        const inFlight = new Map(); // requestKey -> Promise

        function keyOf(request) {
            return JSON.stringify(request);
        }

        async function queryBatch(requests, { noCache = false } = {}) {
            const results = new Array(requests.length);
            const missing = [];
            requests.forEach((request, index) => {
                const key = keyOf(request);
                if (!noCache && cache.has(key)) {
                    results[index] = cache.get(key);
                } else {
                    missing.push({ index, request, key });
                }
            });
            if (missing.length) {
                const fetched = await rpc("/bi/query", {
                    requests: missing.map((m) => m.request),
                });
                missing.forEach((m, i) => {
                    results[m.index] = fetched[i];
                    if (!fetched[i].error) {
                        cache.set(m.key, fetched[i]);
                    }
                });
            }
            return results;
        }

        return {
            queryBatch,

            async query(request, options = {}) {
                const key = keyOf(request);
                if (!options.noCache && cache.has(key)) {
                    return cache.get(key);
                }
                if (inFlight.has(key)) {
                    return inFlight.get(key);
                }
                const promise = queryBatch([request], options).then(([result]) => {
                    inFlight.delete(key);
                    return result;
                });
                inFlight.set(key, promise);
                return promise;
            },

            clearCache(datasetId = null) {
                if (datasetId === null) {
                    cache.clear();
                    return;
                }
                for (const key of [...cache.keys()]) {
                    if (key.includes(`"dataset_id":${datasetId}`)) {
                        cache.delete(key);
                    }
                }
            },
        };
    },
};

registry.category("services").add("bi_data", biDataService);
