/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const NODE_W = 210;
const NODE_H = 96;
const COL_GAP = 300;
const ROW_GAP = 128;
const CANVAS_PAD = 36;

const ROLE_OPTIONS = ["dimension", "measure", "date", "geo", "id"];
const AGG_OPTIONS = ["none", "sum", "avg", "min", "max", "count", "count_distinct"];
const VISIBILITY_OPTIONS = ["visible", "hidden", "sensitive"];

export class ModelerAction extends Component {
    static template = "biz_bi.Modeler";
    static props = { "*": true };
    static displayName = _t("Semantic Modeler");

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.roleOptions = ROLE_OPTIONS;
        this.aggOptions = AGG_OPTIONS;
        this.visibilityOptions = VISIBILITY_OPTIONS;

        this.state = useState({
            datasets: [],
            datasetId: null,
            model: null, // get_modeler_data payload
            selectedNodeId: null,
            fields: [],
            fieldSearch: "",
            drawerOpen: true,
            joinMenuNodeId: null,
            busy: false,
        });

        onWillStart(async () => {
            this.state.datasets = await this.orm.searchRead(
                "bi.dataset", [], ["name", "state"]);
            const params = this.props.action?.params || {};
            const initial = params.dataset_id
                || (this.state.datasets[0] && this.state.datasets[0].id);
            if (initial) {
                await this.loadDataset(initial);
            }
        });
    }

    // ------------------------------------------------------------------
    // Loading
    // ------------------------------------------------------------------

    onDatasetSelectChange(ev) {
        const datasetId = parseInt(ev.target.value);
        if (datasetId) {
            this.loadDataset(datasetId);
        }
    }

    async loadDataset(datasetId) {
        this.state.datasetId = datasetId;
        this.state.joinMenuNodeId = null;
        this.state.model = await this.orm.call(
            "bi.dataset", "get_modeler_data", [[datasetId]]);
        const stillThere = this.state.model.nodes.some(
            (n) => n.id === this.state.selectedNodeId);
        const root = this.state.model.nodes.find((n) => n.is_root);
        await this.selectNode(
            stillThere ? this.state.selectedNodeId : root ? root.id : null);
    }

    async selectNode(nodeId) {
        this.state.selectedNodeId = nodeId;
        this.state.fields = nodeId
            ? await this.orm.searchRead(
                "bi.field", [["node_id", "=", nodeId]],
                ["name", "technical_name", "role", "default_agg", "folder",
                 "visibility", "data_type", "origin"],
                { order: "sequence, id", limit: 600 })
            : [];
    }

    get selectedNode() {
        return (this.state.model?.nodes || []).find(
            (n) => n.id === this.state.selectedNodeId) || null;
    }

    // ------------------------------------------------------------------
    // Layout: BFS depth -> columns, stable row order
    // ------------------------------------------------------------------

    get layout() {
        const model = this.state.model;
        if (!model) {
            return { nodes: [], edges: [], width: 400, height: 300 };
        }
        const childrenOf = {};
        for (const rel of model.relationships) {
            (childrenOf[rel.parent_node_id] ||= []).push(rel);
        }
        const depth = {};
        const order = [];
        const root = model.nodes.find((n) => n.is_root);
        const queue = root ? [root.id] : [];
        if (root) {
            depth[root.id] = 0;
        }
        while (queue.length) {
            const nodeId = queue.shift();
            order.push(nodeId);
            for (const rel of childrenOf[nodeId] || []) {
                if (depth[rel.child_node_id] === undefined) {
                    depth[rel.child_node_id] = depth[nodeId] + 1;
                    queue.push(rel.child_node_id);
                }
            }
        }
        // orphans go to a trailing column
        const maxDepth = Math.max(0, ...Object.values(depth));
        for (const node of model.nodes) {
            if (depth[node.id] === undefined) {
                depth[node.id] = maxDepth + 1;
                order.push(node.id);
            }
        }
        const rowIndex = {};
        const columnCount = {};
        for (const nodeId of order) {
            const d = depth[nodeId];
            rowIndex[nodeId] = columnCount[d] || 0;
            columnCount[d] = rowIndex[nodeId] + 1;
        }
        const positioned = model.nodes.map((node) => ({
            ...node,
            x: CANVAS_PAD + depth[node.id] * COL_GAP,
            y: CANVAS_PAD + rowIndex[node.id] * ROW_GAP,
            hasChildren: !!(childrenOf[node.id] || []).length,
        }));
        const byId = Object.fromEntries(positioned.map((n) => [n.id, n]));
        const edges = model.relationships
            .filter((rel) => byId[rel.parent_node_id] && byId[rel.child_node_id])
            .map((rel) => {
                const parent = byId[rel.parent_node_id];
                const child = byId[rel.child_node_id];
                const x1 = parent.x + NODE_W;
                const y1 = parent.y + NODE_H / 2;
                const x2 = child.x;
                const y2 = child.y + NODE_H / 2;
                const mx = (x1 + x2) / 2;
                return {
                    ...rel,
                    path: `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`,
                    labelX: mx,
                    labelY: (y1 + y2) / 2 - 8,
                    deletable: !byId[rel.child_node_id].hasChildren,
                };
            });
        const width = CANVAS_PAD * 2 + (Math.max(0, ...Object.values(depth)) + 1) * COL_GAP;
        const height = CANVAS_PAD * 2 +
            Math.max(1, ...Object.values(columnCount)) * ROW_GAP;
        return { nodes: positioned, edges, width, height, NODE_W, NODE_H };
    }

    roleSummary(node) {
        const roles = node.roles || {};
        const parts = [];
        if (roles.dimension) parts.push(`${roles.dimension} dim`);
        if (roles.measure) parts.push(`${roles.measure} meas`);
        if (roles.date) parts.push(`${roles.date} date`);
        return parts.join(" · ") || _t("no visible fields");
    }

    // ------------------------------------------------------------------
    // Graph edits
    // ------------------------------------------------------------------

    toggleJoinMenu(nodeId) {
        this.state.joinMenuNodeId =
            this.state.joinMenuNodeId === nodeId ? null : nodeId;
    }

    async addJoin(node, suggestion) {
        this.state.busy = true;
        this.state.joinMenuNodeId = null;
        try {
            await this.orm.call("bi.dataset", "add_suggested_relationship",
                [[this.state.datasetId], node.id, suggestion.parent_field,
                 suggestion.comodel, suggestion.label]);
            await this.loadDataset(this.state.datasetId);
            this.notification.add(
                _t("Joined %s.", suggestion.label), { type: "success" });
        } finally {
            this.state.busy = false;
        }
    }

    async removeEdge(edge) {
        if (!edge.deletable) {
            this.notification.add(
                _t("Remove this entity's own joins first."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            // removing a leaf join removes the joined entity with it
            await this.orm.unlink("bi.dataset.node", [edge.child_node_id]);
            if (this.state.selectedNodeId === edge.child_node_id) {
                this.state.selectedNodeId = null;
            }
            await this.loadDataset(this.state.datasetId);
        } finally {
            this.state.busy = false;
        }
    }

    async rescanNode(node) {
        this.state.busy = true;
        try {
            await this.orm.call("bi.dataset.node", "action_scan_fields",
                [[node.id]]);
            await this.loadDataset(this.state.datasetId);
            await this.selectNode(node.id);
            this.notification.add(_t("Fields rescanned."), { type: "success" });
        } finally {
            this.state.busy = false;
        }
    }

    async publish() {
        this.state.busy = true;
        try {
            await this.orm.call("bi.dataset", "action_publish",
                [[this.state.datasetId]]);
            await this.loadDataset(this.state.datasetId);
            this.notification.add(_t("Dataset published."), { type: "success" });
        } finally {
            this.state.busy = false;
        }
    }

    openExplore() {
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "biz_bi.explore",
            params: { dataset_id: this.state.datasetId },
        });
    }

    // ------------------------------------------------------------------
    // Field curator
    // ------------------------------------------------------------------

    get visibleFields() {
        const query = this.state.fieldSearch.trim().toLowerCase();
        if (!query) {
            return this.state.fields;
        }
        return this.state.fields.filter(
            (f) => f.name.toLowerCase().includes(query)
                || f.technical_name.toLowerCase().includes(query));
    }

    async updateField(field, key, value) {
        await this.orm.write("bi.field", [field.id], { [key]: value });
        field[key] = value;
    }
}

registry.category("actions").add("biz_bi.modeler", ModelerAction);
