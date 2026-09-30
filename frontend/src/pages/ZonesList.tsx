import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, RefreshCw, Filter } from "lucide-react";
import apiClient from "../api/client";
import RiskBadge from "../components/RiskBadge";
import DataTrustBadge from "../components/DataTrustBadge";

export const ZonesList: React.FC = () => {
  const [zones, setZones] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");

  const fetchZones = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (typeFilter) params.zone_type = typeFilter;
      const res = await apiClient.get("/zones", { params });
      setZones(res.data.items || []);
    } catch (err) {
      console.error("Failed to load zones", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchZones();
  }, [statusFilter, typeFilter]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Monitored Zones & Risk Matrix</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Jurisdictional zones under district hazard monitoring with real-time risk assessments
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin="SIMULATED" />
          <button onClick={fetchZones} className="btn btn-secondary btn-sm">
            <RefreshCw size={13} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ padding: 14, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: 13 }}>
            <Filter size={15} />
            Filters:
          </div>

          <div style={{ minWidth: 160 }}>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ padding: "6px 12px", fontSize: 12 }}
            >
              <option value="">All Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="INACTIVE">INACTIVE</option>
            </select>
          </div>

          <div style={{ minWidth: 180 }}>
            <select
              className="form-select"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{ padding: "6px 12px", fontSize: 12 }}
            >
              <option value="">All Zone Types</option>
              <option value="URBAN">URBAN</option>
              <option value="SEMI_URBAN">SEMI-URBAN</option>
              <option value="RURAL">RURAL</option>
              <option value="CRITICAL_INFRASTRUCTURE">CRITICAL INFRASTRUCTURE</option>
            </select>
          </div>
        </div>
      </div>

      {/* Zones Table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Zone Code & Name</th>
              <th>Type</th>
              <th>Current Risk</th>
              <th>Flood Risk</th>
              <th>Landslide Risk</th>
              <th>Sensors</th>
              <th>Active Incidents</th>
              <th>Alerts</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--text-muted)" }}>
                  Loading zones directory...
                </td>
              </tr>
            ) : zones.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "var(--text-muted)" }}>
                  No zones match the selected filters.
                </td>
              </tr>
            ) : (
              zones.map((z) => (
                <tr key={z.id}>
                  <td>
                    <div style={{ fontWeight: 600, color: "var(--text-main)" }}>{z.name}</div>
                    <div style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                      {z.admin_code || `ZONE-${z.id}`}
                    </div>
                  </td>
                  <td>
                    <span className="badge" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid var(--border-subtle)" }}>
                      {z.zone_type}
                    </span>
                  </td>
                  <td><RiskBadge level={z.current_risk_level} /></td>
                  <td><RiskBadge level={z.flood_risk_level} /></td>
                  <td><RiskBadge level={z.landslide_risk_level} /></td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{z.sensor_count} nodes</td>
                  <td style={{ fontFamily: "var(--font-mono)", color: z.active_incident_count > 0 ? "var(--risk-high)" : "inherit" }}>
                    {z.active_incident_count}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", color: z.active_alert_count > 0 ? "var(--risk-crit)" : "inherit" }}>
                    {z.active_alert_count}
                  </td>
                  <td>
                    <Link to={`/zones/${z.id}`} className="btn btn-secondary btn-sm">
                      Intelligence <ExternalLink size={12} />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ZonesList;
