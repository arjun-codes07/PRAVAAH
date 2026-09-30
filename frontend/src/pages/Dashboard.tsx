import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ShieldAlert,
  AlertTriangle,
  Bell,
  Activity,
  Droplets,
  Thermometer,
  Gauge,
  CheckCircle,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  Terminal,
} from "lucide-react";
import apiClient from "../api/client";
import RiskBadge from "../components/RiskBadge";
import DataTrustBadge from "../components/DataTrustBadge";

export const Dashboard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchDashboard = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const res = await apiClient.get("/dashboard/summary");
      setData(res.data);
      setError(null);
    } catch {
      setError("Failed to synchronize with command feed.");
    } finally {
      setLoading(false);
      if (isManual) setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const intervalMs = Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 15000;
    const timer = setInterval(() => fetchDashboard(), intervalMs);
    return () => clearInterval(timer);
  }, []);

  const handleAcknowledgeAlert = async (alertId: number) => {
    try {
      await apiClient.post(`/alerts/${alertId}/acknowledge`);
      fetchDashboard(true);
    } catch (err: any) {
      alert("Failed to acknowledge alert: " + (err.response?.data?.detail || err.message));
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh", color: "var(--text-muted)" }}>
        <RefreshCw size={24} className="animate-spin" style={{ marginRight: 12 }} />
        Synchronizing Crisis Command Feed...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card" style={{ borderLeft: "4px solid var(--risk-crit)" }}>
        <h3>Command Feed Error</h3>
        <p style={{ color: "var(--text-muted)", marginTop: 8 }}>{error || "No data received"}</p>
        <button onClick={() => fetchDashboard(true)} className="btn btn-secondary" style={{ marginTop: 16 }}>
          Retry Connection
        </button>
      </div>
    );
  }

  const {
    risk_counts_by_level = {},
    high_risk_zones = [],
    environmental_indicators = {},
    active_incidents = { count: 0, latest: [], by_severity: {} },
    active_alerts = { count: 0, latest: [], by_severity: {} },
    sensor_health = { active: 0, stale: 0, inactive: 0 },
  } = data;

  const overallRisk =
    (risk_counts_by_level["CRITICAL"] || 0) > 0
      ? "CRITICAL"
      : (risk_counts_by_level["HIGH"] || 0) > 0
      ? "HIGH"
      : (risk_counts_by_level["MODERATE"] || 0) > 0
      ? "MODERATE"
      : "LOW";

  const totalZones = Object.values(risk_counts_by_level as Record<string, number>).reduce((a, b) => a + b, 0);

  return (
    <div>
      {/* Top action / status header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "0.02em" }}>
            Operational Command Center
          </h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Real-time hydro-meteorological early warning & response status for Himachal Pradesh (Mandi District)
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin={data.data_origins_present?.[0] || "SIMULATED"} />
          <button
            onClick={() => fetchDashboard(true)}
            className="btn btn-secondary btn-sm"
            disabled={refreshing}
          >
            <RefreshCw size={13} style={{ animation: refreshing ? "spin 1s linear infinite" : undefined }} />
            {refreshing ? "Refreshing..." : "Sync Feed"}
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid-stats">
        <div className={`stat-card risk-${overallRisk.toLowerCase()}`}>
          <div className="stat-label">Authority Risk Level</div>
          <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 10 }}>
            <RiskBadge level={overallRisk} />
          </div>
          <div className="stat-sub">Model: demo-rule-baseline</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Monitored Zones</div>
          <div className="stat-value">{totalZones || 5}</div>
          <div className="stat-sub">
            {high_risk_zones.length} elevated risk zones
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Active Incidents</div>
          <div className="stat-value" style={{ color: active_incidents.count > 0 ? "var(--risk-high)" : "var(--text-main)" }}>
            {active_incidents.count}
          </div>
          <div className="stat-sub">
            {active_incidents.by_severity?.["CRITICAL"] || 0} critical severity
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Active Alerts</div>
          <div className="stat-value" style={{ color: active_alerts.count > 0 ? "var(--risk-crit)" : "var(--text-main)" }}>
            {active_alerts.count}
          </div>
          <div className="stat-sub">
            {active_alerts.by_severity?.["CRITICAL"] || 0} critical severity
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Sensor Health</div>
          <div className="stat-value" style={{ color: sensor_health.stale > 0 ? "var(--risk-mod)" : "var(--risk-low)" }}>
            {sensor_health.active} / {sensor_health.active + sensor_health.stale + sensor_health.inactive}
          </div>
          <div className="stat-sub">
            {sensor_health.stale} sensor nodes stale
          </div>
        </div>
      </div>

      {/* Environmental Aggregate Indicators */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Activity size={16} style={{ color: "var(--accent)" }} />
            District Environmental Metrics (Mean Live Telemetry)
          </div>
          <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            AGGREGATED FROM ACTIVE VALID OBSERVATIONS
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16 }}>
          <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 14, borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 12 }}>
              <Droplets size={14} style={{ color: "#38bdf8" }} />
              Rainfall (1h Avg)
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 6 }}>
              {environmental_indicators?.avg_rainfall_1h_mm !== null && environmental_indicators?.avg_rainfall_1h_mm !== undefined
                ? `${environmental_indicators.avg_rainfall_1h_mm} mm`
                : "—"}
            </div>
          </div>

          <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 14, borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 12 }}>
              <Gauge size={14} style={{ color: "#60a5fa" }} />
              River Water Level
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 6 }}>
              {environmental_indicators?.avg_water_level_m !== null && environmental_indicators?.avg_water_level_m !== undefined
                ? `${environmental_indicators.avg_water_level_m} m`
                : "—"}
            </div>
          </div>

          <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 14, borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 12 }}>
              <Droplets size={14} style={{ color: "#a78bfa" }} />
              Soil Moisture
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 6 }}>
              {environmental_indicators?.avg_soil_moisture_pct !== null && environmental_indicators?.avg_soil_moisture_pct !== undefined
                ? `${environmental_indicators.avg_soil_moisture_pct}%`
                : "—"}
            </div>
          </div>

          <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 14, borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 12 }}>
              <Thermometer size={14} style={{ color: "#fb923c" }} />
              Temperature
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 6 }}>
              {environmental_indicators?.avg_temperature_c !== null && environmental_indicators?.avg_temperature_c !== undefined
                ? `${environmental_indicators.avg_temperature_c} °C`
                : "—"}
            </div>
          </div>

          <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 14, borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 12 }}>
              <Activity size={14} style={{ color: "#34d399" }} />
              Relative Humidity
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 6 }}>
              {environmental_indicators?.avg_humidity_pct !== null && environmental_indicators?.avg_humidity_pct !== undefined
                ? `${environmental_indicators.avg_humidity_pct}%`
                : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Elevated Zones & Alerts */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20, marginBottom: 24 }}>
        {/* Elevated Risk Zones */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <ShieldAlert size={16} style={{ color: "var(--risk-high)" }} />
              Elevated Risk Zones ({high_risk_zones.length})
            </div>
            <Link to="/zones" className="btn btn-secondary btn-sm">
              All Zones <ArrowRight size={12} />
            </Link>
          </div>

          {high_risk_zones.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
              <CheckCircle size={28} style={{ color: "var(--risk-low)", margin: "0 auto 8px" }} />
              All monitored zones are currently at LOW baseline status.
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Zone</th>
                    <th>Risk</th>
                    <th>Predicted</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {high_risk_zones.map((zone: any) => (
                    <tr key={zone.zone_id}>
                      <td style={{ fontWeight: 600 }}>{zone.zone_name}</td>
                      <td><RiskBadge level={zone.risk_level} /></td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                        {new Date(zone.predicted_at).toLocaleTimeString("en-IN")}
                      </td>
                      <td>
                        <Link to={`/zones/${zone.zone_id}`} className="btn btn-secondary btn-sm">
                          Details <ExternalLink size={11} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Active Alerts */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Bell size={16} style={{ color: "var(--risk-crit)" }} />
              Emergency Alerts ({active_alerts.count})
            </div>
            <Link to="/alerts" className="btn btn-secondary btn-sm">
              Alerts Center <ArrowRight size={12} />
            </Link>
          </div>

          {(!active_alerts.latest || active_alerts.latest.length === 0) ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
              <CheckCircle size={28} style={{ color: "var(--risk-low)", margin: "0 auto 8px" }} />
              No active emergency alerts in this jurisdiction.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {active_alerts.latest.slice(0, 4).map((alt: any) => (
                <div
                  key={alt.id}
                  style={{
                    background: "rgba(0, 0, 0, 0.25)",
                    border: "1px solid var(--border-subtle)",
                    borderLeft: `4px solid ${alt.severity === "CRITICAL" ? "var(--risk-crit)" : "var(--risk-high)"}`,
                    borderRadius: 6,
                    padding: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <RiskBadge level={alt.severity} />
                      <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                        {alt.alert_type} ALERT
                      </span>
                    </div>
                    {alt.status === "ACTIVE" ? (
                      <button
                        onClick={() => handleAcknowledgeAlert(alt.id)}
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: 11 }}
                      >
                        Acknowledge
                      </button>
                    ) : (
                      <span className="badge badge-active" style={{ fontSize: 10 }}>
                        ACKNOWLEDGED
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text-main)", marginBottom: 4 }}>
                    {alt.message}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)", display: "flex", justifyContent: "space-between" }}>
                    <span>Zone #{alt.zone_id}</span>
                    <span>Expires: {alt.expires_at ? new Date(alt.expires_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "Indefinite"}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Active Incidents & Simulator Status */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Active Incidents */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <AlertTriangle size={16} style={{ color: "var(--risk-mod)" }} />
              Active Incident Reports ({active_incidents.count})
            </div>
            <Link to="/incidents" className="btn btn-secondary btn-sm">
              Manage <ArrowRight size={12} />
            </Link>
          </div>

          {(!active_incidents.latest || active_incidents.latest.length === 0) ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
              No open field incidents reported.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {active_incidents.latest.map((inc: any) => (
                <div
                  key={inc.id}
                  style={{
                    background: "rgba(0, 0, 0, 0.25)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: 6,
                    padding: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>
                      #{inc.id} — {inc.incident_type}
                    </span>
                    <RiskBadge level={inc.severity} />
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {inc.description || `Reported at ${new Date(inc.created_at).toLocaleTimeString("en-IN")}`}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "var(--text-dim)" }}>
                    <span>Status: <strong style={{ color: "var(--accent)" }}>{inc.status}</strong></span>
                    <span>Zone #{inc.zone_id}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Simulator Info & Controls */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Terminal size={16} style={{ color: "var(--accent)" }} />
              Telemetry Simulator Integration
            </div>
            <DataTrustBadge origin="SIMULATED" />
          </div>

          <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 14 }}>
            PRAVAAH includes an integrated multi-scenario IoT sensor simulator (`scripts.simulate`) that can push escalation scenarios to the live system:
          </p>

          <div style={{ background: "rgba(0, 0, 0, 0.4)", padding: 12, borderRadius: 6, fontFamily: "var(--font-mono)", fontSize: 11, marginBottom: 14 }}>
            <div style={{ color: "#a3e635", marginBottom: 4 }}># Run Flood Escalation (LOW &rarr; CRITICAL)</div>
            <div style={{ color: "var(--text-main)" }}>.venv\Scripts\python.exe -m scripts.simulate --scenario flood_escalation --steps 5</div>
            
            <div style={{ color: "#a3e635", margin: "10px 0 4px" }}># Run Landslide Escalation</div>
            <div style={{ color: "var(--text-main)" }}>.venv\Scripts\python.exe -m scripts.simulate --scenario landslide_escalation --steps 5</div>

            <div style={{ color: "#a3e635", margin: "10px 0 4px" }}># Test Sensor Staleness Drop</div>
            <div style={{ color: "var(--text-main)" }}>.venv\Scripts\python.exe -m scripts.simulate --silence-node HP-MANDI-001</div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: "var(--text-muted)" }}>
            <Activity size={14} style={{ color: "var(--risk-low)" }} />
            Automatic ingestion recalculates zone risk and supersedes older predictions in real-time.
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
