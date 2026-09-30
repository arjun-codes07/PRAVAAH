import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ShieldAlert,
  ArrowLeft,
  History,
  Truck,
  Layers,
  RefreshCw,
} from "lucide-react";
import apiClient from "../api/client";
import RiskBadge from "../components/RiskBadge";
import DataTrustBadge from "../components/DataTrustBadge";
import StaleIndicator from "../components/StaleIndicator";

export const ZoneDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [zone, setZone] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [radiusM, setRadiusM] = useState<number>(5000);

  const fetchZoneData = async () => {
    setLoading(true);
    try {
      const [resZone, resHistory] = await Promise.all([
        apiClient.get(`/zones/${id}`, { params: { include_geometry: true, nearby_radius_m: radiusM } }),
        apiClient.get(`/zones/${id}/risk-history`, { params: { limit: 10 } }),
      ]);
      setZone(resZone.data);
      setHistory(resHistory.data.items || []);
    } catch (err) {
      console.error("Failed to load zone detail", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchZoneData();
  }, [id, radiusM]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "50vh", color: "var(--text-muted)" }}>
        <RefreshCw size={22} className="animate-spin" style={{ marginRight: 10 }} />
        Loading Zone Intelligence...
      </div>
    );
  }

  if (!zone) {
    return (
      <div className="card">
        <h3>Zone Not Found</h3>
        <p style={{ color: "var(--text-muted)", marginTop: 8 }}>The requested zone does not exist or access is restricted.</p>
        <Link to="/zones" className="btn btn-secondary" style={{ marginTop: 14 }}>
          &larr; Back to Zones
        </Link>
      </div>
    );
  }

  const risk = zone.current_risk;

  return (
    <div>
      {/* Top breadcrumb & header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <Link to="/zones" style={{ color: "var(--text-muted)", textDecoration: "none", fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
              <ArrowLeft size={14} /> Zones
            </Link>
            <span style={{ color: "var(--border-subtle)" }}>/</span>
            <span style={{ color: "var(--text-dim)", fontSize: 13 }}>{zone.admin_code || `ZONE-${zone.zone_id}`}</span>
          </div>

          <h1 style={{ fontSize: 24, fontWeight: 700 }}>
            {zone.name}
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
            <span className="badge" style={{ background: "rgba(255,255,255,0.06)" }}>{zone.zone_type}</span>
            <span className="badge badge-active">{zone.status}</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin={zone.data_origin || "SIMULATED"} />
          <button onClick={fetchZoneData} className="btn btn-secondary btn-sm">
            <RefreshCw size={13} />
            Refresh Intelligence
          </button>
        </div>
      </div>

      {/* Primary Risk Assessment Banner */}
      <div className="card" style={{
        borderLeft: `5px solid ${risk ? (risk.overall_risk_level === 'CRITICAL' ? 'var(--risk-crit)' : risk.overall_risk_level === 'HIGH' ? 'var(--risk-high)' : risk.overall_risk_level === 'MODERATE' ? 'var(--risk-mod)' : 'var(--risk-low)') : 'var(--border-subtle)'}`,
        background: "linear-gradient(180deg, rgba(0, 0, 0, 0.3), var(--bg-card))",
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em", marginBottom: 4 }}>
              Active Hazard Assessment
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <RiskBadge level={risk?.overall_risk_level} />
              <span style={{ fontSize: 14, color: "var(--text-muted)" }}>
                Flood: <strong style={{ color: "var(--text-main)" }}>{risk?.flood_risk_level || "LOW"}</strong> | Landslide: <strong style={{ color: "var(--text-main)" }}>{risk?.landslide_risk_level || "LOW"}</strong>
              </span>
            </div>
          </div>

          <div style={{ textAlign: "right", fontSize: 12, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
            <div>Model: {risk?.model_name || "demo-rule-baseline"}</div>
            <div>Predicted: {risk ? new Date(risk.predicted_at).toLocaleTimeString("en-IN") : "—"}</div>
            <div>Valid Horizon: {risk?.horizon_minutes || 360} minutes</div>
          </div>
        </div>

        {/* Advisory Action Notice */}
        <div style={{
          marginTop: 16,
          padding: 14,
          background: "rgba(0, 0, 0, 0.3)",
          borderRadius: 6,
          border: "1px solid var(--border-subtle)",
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--accent)", marginBottom: 4 }}>
            Operational Advisory (Decision Support — Not Autonomous Evacuation)
          </div>
          <div style={{ fontSize: 13, color: "var(--text-main)" }}>
            {risk?.recommended_action || "Continue routine monitoring of environmental indicators."}
          </div>
        </div>
      </div>

      {/* Grid: Explainability Factors & Terrain */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20, marginBottom: 24 }}>
        {/* Risk Explanations */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <ShieldAlert size={16} style={{ color: "var(--accent)" }} />
              Key Contributing Factors & Explainability
            </div>
            <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
              MODEL WEIGHT CONTRIBUTIONS
            </span>
          </div>

          {(!zone.top_factors || zone.top_factors.length === 0) ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
              No detailed explanation factors generated.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {zone.top_factors.map((f: any) => {
                const pct = Math.min(100, Math.round((f.contribution || 0) * 100));
                return (
                  <div key={f.id} style={{ background: "rgba(0, 0, 0, 0.2)", padding: 12, borderRadius: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{f.factor_name}</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--accent)" }}>
                        {f.factor_value !== null ? `${f.factor_value} ${f.unit || ""}` : ""} ({pct}% weight)
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div style={{ width: "100%", height: 6, background: "rgba(255, 255, 255, 0.08)", borderRadius: 3, overflow: "hidden", marginBottom: 6 }}>
                      <div
                        style={{
                          width: `${pct}%`,
                          height: "100%",
                          background: pct > 60 ? "var(--risk-crit)" : pct > 30 ? "var(--risk-high)" : "var(--accent)",
                          borderRadius: 3,
                        }}
                      />
                    </div>

                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {f.explanation_text}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Terrain & Latest Observation */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Layers size={16} style={{ color: "var(--accent)" }} />
              Terrain Context & Environmental Baseline
            </div>
          </div>

          {zone.terrain && zone.terrain.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
              <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 12, borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase" }}>Average Slope</div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 4 }}>
                  {zone.terrain[0].slope_deg}°
                </div>
              </div>

              <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 12, borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase" }}>Susceptibility Score</div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: 4 }}>
                  {zone.terrain[0].susceptibility_score}
                </div>
              </div>
            </div>
          )}

          {/* Connected Sensors in Zone */}
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--text-muted)" }}>
            Assigned Sensor Nodes ({zone.sensors?.length || 0})
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(zone.sensors || []).map((sn: any) => (
              <div
                key={sn.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "rgba(0, 0, 0, 0.25)",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div>
                  <span style={{ fontWeight: 600, fontFamily: "var(--font-mono)", fontSize: 12 }}>{sn.node_id}</span>
                  <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: 8 }}>{sn.sensor_type}</span>
                </div>
                <StaleIndicator isStale={sn.is_stale} lastSeenAt={sn.last_seen_at} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Historical Predictions Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <History size={16} style={{ color: "var(--accent)" }} />
            Risk Assessment History & Prediction Supersession
          </div>
          <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
            AUDITED TIME-SERIES PREDICTIONS
          </span>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Predicted At</th>
                <th>Overall</th>
                <th>Flood</th>
                <th>Landslide</th>
                <th>Model</th>
                <th>Status</th>
                <th>Origin</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>
                    No prediction history recorded for this zone.
                  </td>
                </tr>
              ) : (
                history.map((h) => (
                  <tr key={h.id}>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {new Date(h.predicted_at).toLocaleString("en-IN", { hour12: false })}
                    </td>
                    <td><RiskBadge level={h.overall_risk_level} /></td>
                    <td><RiskBadge level={h.flood_risk_level} /></td>
                    <td><RiskBadge level={h.landslide_risk_level} /></td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>{h.model_name}</td>
                    <td>
                      <span className={`badge ${h.status === 'ACTIVE' ? 'badge-active' : ''}`} style={{
                        background: h.status === 'ACTIVE' ? undefined : 'rgba(255,255,255,0.05)',
                        color: h.status === 'ACTIVE' ? undefined : 'var(--text-dim)',
                      }}>
                        {h.status}
                      </span>
                    </td>
                    <td><DataTrustBadge origin={h.data_origin} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Proximity Rescue Resources Finder */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Truck size={16} style={{ color: "var(--accent)" }} />
            Nearby Emergency Rescue Resources (Spatial Distance Query)
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Search Radius:</span>
            <select
              className="form-select"
              value={radiusM}
              onChange={(e) => setRadiusM(Number(e.target.value))}
              style={{ padding: "4px 8px", fontSize: 12, width: 120 }}
            >
              <option value={3000}>3 km</option>
              <option value={5000}>5 km</option>
              <option value={10000}>10 km</option>
              <option value={20000}>20 km</option>
            </select>
          </div>
        </div>

        {(!zone.nearby_resources || zone.nearby_resources.length === 0) ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
            No registered rescue resources found within {radiusM / 1000} km of zone boundaries.
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Resource Name</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Distance from Zone</th>
                  <th>Provenance</th>
                </tr>
              </thead>
              <tbody>
                {zone.nearby_resources.map((r: any) => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600 }}>{r.name}</td>
                    <td>{r.resource_type}</td>
                    <td>
                      <span className={`badge ${r.status === 'AVAILABLE' ? 'badge-active' : 'badge-stale'}`}>
                        {r.status}
                      </span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--accent)" }}>
                      {r.distance_m < 1000 ? `${r.distance_m} m` : `${(r.distance_m / 1000).toFixed(2)} km`}
                    </td>
                    <td><DataTrustBadge origin={r.data_origin} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ZoneDetail;
