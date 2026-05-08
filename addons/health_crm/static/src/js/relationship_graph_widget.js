/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * D3.js Force-Directed Relationship Network Graph Widget
 * Section 2.2 - Option B: Network Diagram Visualization
 *
 * Displays patients and representatives as nodes connected by relationship edges
 * Color-coded by role, with primary relationships highlighted
 */
export class RelationshipGraphWidget extends Component {
    static template = "health_crm.RelationshipGraphWidget";
    static props = {
        record: Object,
        name: String,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        console.log("=== RelationshipGraphWidget SETUP START ===");
        console.log("All props received:", JSON.stringify(Object.keys(this.props)));
        console.log("Props.name:", this.props.name);
        console.log("Props.record exists:", !!this.props.record);
        console.log("Props.record.data exists:", !!this.props.record?.data);

        this.orm = useService("orm");
        this.svgRef = useRef("relationshipGraph");

        this.state = useState({
            loading: true,
            nodes: [],
            links: [],
            error: null,
        });

        onWillStart(async () => {
            console.log("=== onWillStart - Loading data ===");
            try {
                await this.loadRelationshipData();
            } catch (error) {
                console.error("Error in onWillStart:", error);
                this.state.error = error.message;
                this.state.loading = false;
            }
        });

        onMounted(() => {
            console.log("=== onMounted - Rendering graph ===");
            try {
                this.renderGraph();
            } catch (error) {
                console.error("Error in onMounted:", error);
            }
        });

        console.log("=== RelationshipGraphWidget SETUP END ===");
    }

    t(text) {
        return _t(text);
    }

    /**
     * Load relationship data from the field value
     */
    async loadRelationshipData() {
        try {
            console.log("=== loadRelationshipData START ===");

            // Get relationship IDs from the field value (StaticList)
            const fieldValue = this.props.record.data[this.props.name];
            console.log("Field value:", fieldValue);
            console.log("Field value type:", fieldValue?.constructor?.name);

            // Extract relationship IDs from StaticList
            let relationshipIds = [];
            if (fieldValue && fieldValue.currentIds) {
                relationshipIds = fieldValue.currentIds;
            }

            console.log("Relationship IDs:", relationshipIds);

            if (!relationshipIds || relationshipIds.length === 0) {
                console.log("No relationships found");
                this.state.nodes = [];
                this.state.links = [];
                this.state.loading = false;
                return;
            }

            // Load full relationship records
            const relationships = await this.orm.read(
                "health.client.relation",
                relationshipIds,
                [
                    "client_id",
                    "representative_id",
                    "role",
                    "relationship_type",
                    "is_primary",
                    "financial_responsibility"
                ]
            );

            // Build nodes and links for D3.js
            const nodesMap = new Map();
            const links = [];

            relationships.forEach(rel => {
                // Add client node
                if (!nodesMap.has(rel.client_id[0])) {
                    nodesMap.set(rel.client_id[0], {
                        id: rel.client_id[0],
                        name: rel.client_id[1],
                        type: 'patient',
                        group: 1
                    });
                }

                // Add representative node
                if (!nodesMap.has(rel.representative_id[0])) {
                    nodesMap.set(rel.representative_id[0], {
                        id: rel.representative_id[0],
                        name: rel.representative_id[1],
                        type: 'representative',
                        group: 2
                    });
                }

                // Add link
                links.push({
                    source: rel.client_id[0],
                    target: rel.representative_id[0],
                    role: rel.role,
                    relationship_type: rel.relationship_type || '',
                    is_primary: rel.is_primary,
                    financial_responsibility: rel.financial_responsibility || 0,
                    relationshipId: rel.id
                });
            });

            this.state.nodes = Array.from(nodesMap.values());
            this.state.links = links;
            this.state.loading = false;
        } catch (error) {
            console.error("Error loading relationship data:", error);
            this.state.loading = false;
        }
    }

    /**
     * Render D3.js force-directed graph
     */
    renderGraph() {
        if (this.state.loading || !this.svgRef.el) return;

        // Import D3 from CDN or ensure it's loaded
        if (typeof d3 === 'undefined') {
            console.error("D3.js not loaded. Please include D3.js library.");
            return;
        }

        const svg = d3.select(this.svgRef.el);
        const width = this.svgRef.el.clientWidth || 800;
        const height = this.svgRef.el.clientHeight || 600;

        svg.selectAll("*").remove(); // Clear previous render

        // Color scheme for roles
        const roleColors = {
            'caregiver': '#28a745',      // Green
            'payer': '#17a2b8',          // Blue
            'referrer': '#ffc107',       // Yellow
            'emergency_contact': '#dc3545', // Red
            'legal_guardian': '#6f42c1', // Purple
            'default': '#6c757d'         // Gray
        };

        // Create force simulation
        const simulation = d3.forceSimulation(this.state.nodes)
            .force("link", d3.forceLink(this.state.links)
                .id(d => d.id)
                .distance(150))
            .force("charge", d3.forceManyBody().strength(-400))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(50));

        // Create arrow markers for directed edges
        svg.append("defs").selectAll("marker")
            .data(Object.keys(roleColors))
            .join("marker")
            .attr("id", d => `arrow-${d}`)
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 25)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("fill", d => roleColors[d])
            .attr("d", "M0,-5L10,0L0,5");

        // Create links
        const link = svg.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(this.state.links)
            .join("line")
            .attr("stroke", d => roleColors[d.role] || roleColors.default)
            .attr("stroke-width", d => d.is_primary ? 3 : 1.5)
            .attr("stroke-opacity", 0.6)
            .attr("marker-end", d => `url(#arrow-${d.role})`)
            .style("cursor", "pointer");

        // Create nodes
        const node = svg.append("g")
            .attr("class", "nodes")
            .selectAll("g")
            .data(this.state.nodes)
            .join("g")
            .call(this.drag(simulation));

        // Add circles for nodes
        node.append("circle")
            .attr("r", d => d.type === 'patient' ? 20 : 15)
            .attr("fill", d => d.type === 'patient' ? '#1565C0' : '#42A5F5')
            .attr("stroke", "#fff")
            .attr("stroke-width", 2)
            .style("cursor", "pointer");

        // Add labels
        node.append("text")
            .text(d => d.name.length > 20 ? d.name.substring(0, 20) + '...' : d.name)
            .attr("x", 0)
            .attr("y", 30)
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .attr("fill", "#333");

        // Add icon to distinguish patient vs representative
        node.append("text")
            .text(d => d.type === 'patient' ? '👤' : '👥')
            .attr("x", 0)
            .attr("y", 5)
            .attr("text-anchor", "middle")
            .attr("font-size", "16px");

        // Tooltips
        const tooltip = d3.select("body").append("div")
            .attr("class", "relationship-tooltip")
            .style("position", "absolute")
            .style("visibility", "hidden")
            .style("background", "#fff")
            .style("border", "1px solid #ddd")
            .style("border-radius", "4px")
            .style("padding", "8px")
            .style("font-size", "12px")
            .style("box-shadow", "0 2px 8px rgba(0,0,0,0.15)")
            .style("z-index", "10000");

        // Node tooltips
        node.on("mouseover", (event, d) => {
            tooltip.html(`
                <strong>${d.name}</strong><br/>
                Type: ${d.type === 'patient' ? 'Patient' : 'Representative'}
            `)
            .style("visibility", "visible");
        })
        .on("mousemove", (event) => {
            tooltip.style("top", (event.pageY - 10) + "px")
                   .style("left", (event.pageX + 10) + "px");
        })
        .on("mouseout", () => {
            tooltip.style("visibility", "hidden");
        });

        // Link tooltips
        link.on("mouseover", (event, d) => {
            tooltip.html(`
                <strong>Role:</strong> ${d.role.replace('_', ' ')}<br/>
                <strong>Type:</strong> ${d.relationship_type.replace('_', ' ')}<br/>
                ${d.is_primary ? '<strong>PRIMARY</strong><br/>' : ''}
                ${d.financial_responsibility > 0 ? `<strong>Financial:</strong> ${d.financial_responsibility}%` : ''}
            `)
            .style("visibility", "visible");
        })
        .on("mousemove", (event) => {
            tooltip.style("top", (event.pageY - 10) + "px")
                   .style("left", (event.pageX + 10) + "px");
        })
        .on("mouseout", () => {
            tooltip.style("visibility", "hidden");
        });

        // Update positions on simulation tick
        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node.attr("transform", d => `translate(${d.x},${d.y})`);
        });

        // Legend
        const legend = svg.append("g")
            .attr("class", "legend")
            .attr("transform", `translate(20, 20)`);

        const legendItems = [
            { label: 'Caregiver', color: roleColors.caregiver },
            { label: 'Payer', color: roleColors.payer },
            { label: 'Referrer', color: roleColors.referrer },
            { label: 'Emergency', color: roleColors.emergency_contact },
            { label: 'Legal Guardian', color: roleColors.legal_guardian },
        ];

        legendItems.forEach((item, i) => {
            const legendRow = legend.append("g")
                .attr("transform", `translate(0, ${i * 20})`);

            legendRow.append("line")
                .attr("x1", 0)
                .attr("x2", 20)
                .attr("y1", 10)
                .attr("y2", 10)
                .attr("stroke", item.color)
                .attr("stroke-width", 3);

            legendRow.append("text")
                .attr("x", 25)
                .attr("y", 14)
                .attr("font-size", "11px")
                .text(item.label);
        });
    }

    /**
     * Drag behavior for nodes
     */
    drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }

        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }

        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }

        return d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended);
    }
}

registry.category("fields").add("relationship_graph", {
    component: RelationshipGraphWidget,
    supportedTypes: ["one2many"],
});
