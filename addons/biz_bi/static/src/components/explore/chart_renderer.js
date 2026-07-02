/** @odoo-module **/

import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl";
import { buildChartOption } from "../../core/chart_option_builder";
import { user } from "@web/core/user";

/**
 * Dumb ECharts host: {envelope, config} -> rendered chart.
 * Owns init / resize (ResizeObserver) / dispose. Emits datapoint clicks
 * with dimension keys so cross-filtering can hook in later.
 */
export class ChartRenderer extends Component {
    static template = "biz_bi.ChartRenderer";
    static props = {
        envelope: { type: Object },
        config: { type: Object },
        onDatapointClick: { type: Function, optional: true },
    };

    setup() {
        this.containerRef = useRef("container");
        this.chart = null;

        onMounted(() => {
            this._init();
            this.resizeObserver = new ResizeObserver(() => {
                if (this.chart) {
                    this.chart.resize();
                }
            });
            this.resizeObserver.observe(this.containerRef.el);
        });

        onWillUpdateProps((nextProps) => {
            this._render(nextProps);
        });

        onWillUnmount(() => {
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
            if (this.chart) {
                this.chart.dispose();
                this.chart = null;
            }
        });
    }

    _init() {
        /* global echarts */
        this.chart = echarts.init(this.containerRef.el, null, { renderer: "canvas" });
        this.chart.on("click", (params) => {
            if (this.props.onDatapointClick) {
                this.props.onDatapointClick({
                    category: params.name,
                    seriesName: params.seriesName,
                    value: params.value,
                });
            }
        });
        this._render(this.props);
    }

    _render(props) {
        if (!this.chart || !props.envelope || props.envelope.error) {
            return;
        }
        const option = buildChartOption(props.envelope, props.config, user.lang || "en_US");
        this.chart.setOption(option, { notMerge: true });
    }
}
