import React, { useState, useEffect } from "react";
import {
  Users,
  Box,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-react";
import apiClient from "../api/client";
import DataTrustBadge from "../components/DataTrustBadge";

export const Response: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"TEAMS" | "RESOURCES">("TEAMS");
  const [teams, setTeams] = useState<any[]>([]);
  const [resources, setResources] = useState<any[]>([]);

  // Proximity Search state
  const [nearLat, setNearLat] = useState<string>("31.710");
  const [nearLon, setNearLon] = useState<string>("76.930");
  const [radiusM, setRadiusM] = useState<number>(10000);

  const fetchResponseData = async () => {
    try {
      const [resTeams, resResources] = await Promise.all([
        apiClient.get("/response/teams"),
        apiClient.get("/response/resources", {
          params: {
            near_lat: nearLat ? parseFloat(nearLat) : undefined,
            near_lon: nearLon ? parseFloat(nearLon) : undefined,
            radius_m: radiusM,
          },
        }),
      ]);
      setTeams(resTeams.data || []);
      setResources(resResources.data || []);
    } catch (err) {
      console.error("Failed to load response data", err);
    }
  };

  useEffect(() => {
    fetchResponseData();
  }, [activeTab, radiusM]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Rescue Assets & Field Coordination</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Disaster response teams, heavy equipment, logistics inventory, and real-time dispatch tracking
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin="SIMULATED" />
          <button onClick={fetchResponseData} className="btn btn-secondary btn-sm">
            <RefreshCw size={13} />
            Refresh Assets
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <button
          onClick={() => setActiveTab("TEAMS")}
          className={`btn ${activeTab === "TEAMS" ? "btn-primary" : "btn-secondary"}`}
        >
          <Users size={15} />
          Rescue Teams ({teams.length})
        </button>
        <button
          onClick={() => setActiveTab("RESOURCES")}
          className={`btn ${activeTab === "RESOURCES" ? "btn-primary" : "btn-secondary"}`}
        >
          <Box size={15} />
          Rescue Equipment & Resources ({resources.length})
        </button>
      </div>

      {activeTab === "TEAMS" ? (
        /* Rescue Teams View */
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 18 }}>
          {teams.map((t) => (
            <div key={t.id} className="card" style={{ marginBottom: 0 }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 700 }}>{t.name}</h3>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                    Type: <strong style={{ color: "var(--accent)" }}>{t.team_type}</strong>
                  </div>
                </div>
                <span className={`badge ${t.status === "AVAILABLE" ? "badge-active" : "badge-stale"}`}>
                  {t.status}
                </span>
              </div>

              <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: 10, borderRadius: 6, fontSize: 12, marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ color: "var(--text-muted)" }}>Active Deployments:</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{t.active_assignment_count}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>GPS Location:</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {t.latitude ? `${t.latitude.toFixed(3)}, ${t.longitude.toFixed(3)}` : "Base HQ"}
                  </span>
                </div>
              </div>

              <div style={{ fontSize: 11, color: "var(--text-dim)" }}>
                Updated: {new Date(t.updated_at).toLocaleTimeString("en-IN")}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Rescue Resources View */
        <div>
          {/* Proximity Filter Bar */}
          <div className="card" style={{ padding: 14, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 13 }}>
                <MapPin size={15} style={{ color: "var(--accent)" }} />
                Spatial Proximity Search:
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-dim)" }}>Lat:</span>
                <input
                  type="text"
                  className="form-input"
                  value={nearLat}
                  onChange={(e) => setNearLat(e.target.value)}
                  style={{ width: 90, padding: "5px 8px", fontSize: 12 }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-dim)" }}>Lon:</span>
                <input
                  type="text"
                  className="form-input"
                  value={nearLon}
                  onChange={(e) => setNearLon(e.target.value)}
                  style={{ width: 90, padding: "5px 8px", fontSize: 12 }}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-dim)" }}>Radius:</span>
                <select
                  className="form-select"
                  value={radiusM}
                  onChange={(e) => setRadiusM(Number(e.target.value))}
                  style={{ width: 110, padding: "5px 8px", fontSize: 12 }}
                >
                  <option value={5000}>5 km</option>
                  <option value={10000}>10 km</option>
                  <option value={20000}>20 km</option>
                  <option value={50000}>50 km</option>
                </select>
              </div>

              <button onClick={fetchResponseData} className="btn btn-secondary btn-sm">
                <Search size={12} /> Apply Filter
              </button>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Resource Name</th>
                  <th>Type</th>
                  <th>Quantity</th>
                  <th>Status</th>
                  <th>Assigned Team</th>
                  <th>Distance (from point)</th>
                </tr>
              </thead>
              <tbody>
                {resources.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", padding: 24, color: "var(--text-muted)" }}>
                      No resources found matching the spatial criteria.
                    </td>
                  </tr>
                ) : (
                  resources.map((r) => (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 600 }}>{r.name}</td>
                      <td>
                        <span className="badge" style={{ background: "rgba(255,255,255,0.06)" }}>
                          {r.resource_type}
                        </span>
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{r.quantity} units</td>
                      <td>
                        <span className={`badge ${r.status === "AVAILABLE" ? "badge-active" : "badge-stale"}`}>
                          {r.status}
                        </span>
                      </td>
                      <td style={{ color: r.team_name ? "var(--text-main)" : "var(--text-dim)" }}>
                        {r.team_name || "Unassigned"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", color: "var(--accent)" }}>
                        {r.distance_m !== null ? (
                          r.distance_m < 1000 ? `${r.distance_m} m` : `${(r.distance_m / 1000).toFixed(2)} km`
                        ) : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Response;
