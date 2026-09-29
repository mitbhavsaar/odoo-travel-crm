/** @odoo-module **/

import { Component, proxy, onWillStart, onMounted, signal } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function useRef(name) {
    const s = signal(null);
    return {
        get el() {
            return s();
        },
        set(val) {
            s.set(val);
        },
    };
}

export class TravelCrmDashboard extends Component {
    static template = "travel_crm.TravelCrmDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.donutChartCanvas = useRef("donutChartCanvas");
        this.trendChartCanvas = useRef("trendChartCanvas");
        this.stageChartCanvas = useRef("stageChartCanvas");
        this.revenueChartCanvas = useRef("revenueChartCanvas");
        this.userPerfChartCanvas = useRef("userPerfChartCanvas");

        this.charts = {};

        this.state = proxy({
            isLoading: true,
            sidebarCollapsed: false,
            activeTab: "dashboard",
            dateRange: "this_month",
            data: {
                kpis: { open: 0, in_progress: 0, converted: 0, lost: 0 },
                calls: { attempted: 0, connected: 0, rate: 0 },
                pinned_campaigns: [],
                lead_source_summary: { total: 0, items: [], labels: [], data: [], colors: [] },
                stage_analysis: { labels: [], data: [], colors: [] },
                trend_analysis: { labels: [], total: [], converted: [] },
                revenue_summary: { labels: [], data: [] },
                user_performance: { labels: [], data: [] },
                recent_leads: [],
                recent_calls: [],
                recent_contacts: [],
                recent_activities: [],
                settings_info: {},
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            if (this.state.activeTab === "dashboard") {
                this.renderAllCharts();
            }
        });
    }

    async loadData() {
        this.state.isLoading = true;
        try {
            const res = await this.orm.call("travel.crm.dashboard", "get_dashboard_data", [], {
                date_range: this.state.dateRange,
            });
            this.state.data = res;
        } catch (error) {
            console.error("Dashboard RPC Error:", error);
            this.notification.add("Failed to load dashboard metrics", { type: "danger" });
        } finally {
            this.state.isLoading = false;
            if (this.state.activeTab === "dashboard") {
                setTimeout(() => {
                    this.renderAllCharts();
                }, 100);
            }
        }
    }

    async onDateRangeChange(ev) {
        this.state.dateRange = ev.target.value;
        await this.loadData();
    }

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
    }

    onNavClick(tabName) {
        this.state.activeTab = tabName;
        if (tabName === "dashboard") {
            setTimeout(() => {
                this.renderAllCharts();
            }, 100);
        }
    }

    destroyCharts() {
        Object.keys(this.charts).forEach((key) => {
            if (this.charts[key]) {
                this.charts[key].destroy();
                delete this.charts[key];
            }
        });
    }

    renderAllCharts() {
        if (!window.Chart) {
            console.warn("Chart.js not loaded in window.");
            return;
        }
        this.destroyCharts();

        this.renderDonutChart();
        this.renderTrendChart();
        this.renderStageChart();
        this.renderRevenueChart();
        this.renderUserPerfChart();
    }

    renderDonutChart() {
        const canvas = this.donutChartCanvas.el;
        if (!canvas) return;

        const srcData = this.state.data.lead_source_summary;
        this.charts.donut = new window.Chart(canvas, {
            type: "doughnut",
            data: {
                labels: srcData.labels,
                datasets: [
                    {
                        data: srcData.data,
                        backgroundColor: srcData.colors,
                        borderWidth: 2,
                        borderColor: "#FFFFFF",
                        hoverOffset: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "72%",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const val = context.raw || 0;
                                const total = srcData.total || 1;
                                const pct = ((val / total) * 100).toFixed(1);
                                return ` ${context.label}: ${val} (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    renderTrendChart() {
        const canvas = this.trendChartCanvas.el;
        if (!canvas) return;

        const trend = this.state.data.trend_analysis;
        this.charts.trend = new window.Chart(canvas, {
            type: "line",
            data: {
                labels: trend.labels,
                datasets: [
                    {
                        label: "Total Leads",
                        data: trend.total,
                        borderColor: "#7141C8",
                        backgroundColor: "rgba(113, 65, 200, 0.1)",
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                    },
                    {
                        label: "Converted Leads",
                        data: trend.converted,
                        borderColor: "#22C55E",
                        backgroundColor: "rgba(34, 197, 94, 0.05)",
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" },
                },
                scales: {
                    y: { grid: { color: "#F1F5F9" } },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    renderStageChart() {
        const canvas = this.stageChartCanvas.el;
        if (!canvas) return;

        const stage = this.state.data.stage_analysis;
        this.charts.stage = new window.Chart(canvas, {
            type: "bar",
            data: {
                labels: stage.labels,
                datasets: [
                    {
                        label: "Leads",
                        data: stage.data,
                        backgroundColor: stage.colors,
                        borderRadius: 8,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: { grid: { color: "#F1F5F9" } },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    renderRevenueChart() {
        const canvas = this.revenueChartCanvas.el;
        if (!canvas) return;

        const rev = this.state.data.revenue_summary;
        this.charts.revenue = new window.Chart(canvas, {
            type: "bar",
            data: {
                labels: rev.labels,
                datasets: [
                    {
                        label: "Revenue (₹)",
                        data: rev.data,
                        backgroundColor: "#3B82F6",
                        borderRadius: 8,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: { grid: { color: "#F1F5F9" } },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    renderUserPerfChart() {
        const canvas = this.userPerfChartCanvas.el;
        if (!canvas) return;

        const user = this.state.data.user_performance;
        this.charts.userPerf = new window.Chart(canvas, {
            type: "bar",
            data: {
                labels: user.labels,
                datasets: [
                    {
                        label: "Leads Converted",
                        data: user.data,
                        backgroundColor: "#10B981",
                        borderRadius: 8,
                    },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: { grid: { color: "#F1F5F9" } },
                    y: { grid: { display: false } },
                },
            },
        });
    }

    unpinCampaign(campaignId) {
        this.state.data.pinned_campaigns = this.state.data.pinned_campaigns.filter((c) => c.id !== campaignId);
        this.notification.add("Campaign unpinned", { type: "info" });
    }

    openCampaignReport() {
        this.action.doAction("utm.utm_campaign_action");
    }

    createCampaign() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "utm.campaign",
            views: [[false, "form"]],
            target: "new",
        });
    }

    openCampaignsView() {
        this.action.doAction("utm.utm_campaign_action");
    }

    onUploadLeadsClick() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openLeadsByState(stateType) {
        this.action.doAction("travel_crm.action_travel_pipeline");
    }

    openUserCallReport() {
        this.action.doAction("travel_crm.action_travel_call_log");
    }

    openUserLoginReport() {
        this.action.doAction("travel_crm.action_travel_leaderboard");
    }

    openManageUsers() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    onSupportClick() {
        this.notification.add("Need assistance? Contact 361 Techno Consulting Support.", { type: "info" });
    }

    onQuickActionClick() {
        this.notification.add("Quick Rocket Action Triggered!", { type: "success" });
    }

    openLeadRecord(leadId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            res_id: leadId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openCallRecord(callId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "travel.call.log",
            res_id: callId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("travel_crm.dashboard", TravelCrmDashboard);
