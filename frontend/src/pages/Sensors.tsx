import React, { useState, useEffect } from "react";
import {
  Radio,
  Database,
  RefreshCw,
  X,
  History,
} from "lucide-react";
import apiClient from "../api/client";
import StaleIndicator from "../components/StaleIndicator";
import DataTrustBadge from "../components/DataTrustBadge";

export const Sensors: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"SENSORS" | "SOURCES">("SENSORS");
  const [sensors, setSensors] = useState<any[]>([]);
  const [sources, setSources] = useState<any[]>([]);

  // Sensor Readings Modal
  const [selectedSensor, setSelectedSensor] = useState<string | null>(null);
  const [readings, setReadings] = useState<any[]>([]);
  const [readingsLoading, setReadingsLoading] = useState<boolean>(false);

  const fetchSensorData = async () => {
    try {
      const [resSensors, resSources] = await Promise.all([
        apiClient.get("/sensors"),
        apiClient.get("/data-sources"),
      ]);
      setSensors(resSensors.data.items || []);
      setSources(resSources.data || []);
    } catch (err) {
      console.error("Failed to load sensors", err);
    }
  };

  useEffect(() => {
    fetchSensorData();
  }, []);

  const openSensorReadings = async (nodeId: string) => {
    setSelectedSensor(nodeId);
    setReadingsLoading(true);
    try {
      const res = await apiClient.get(`/sensors/${nodeId}/readings`, { params: { limit: 20 } });
      setReadings(res.data.items || []);
    } catch (err) {
      alert("Failed to load readings for " + nodeId);
    } finally {
      setReadingsLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Sensors & Telemetry Monitoring</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Real-time IoT telemetry ingestion feeds, sensor node staleness tracking, and data provenance
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin="SIMULATED" />
          <button onClick={fetchSensorData} className="btn btn-secondary btn-sm">
            <RefreshCw size={13} />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <button
          onClick={() => setActiveTab("SENSORS")}
          className={`btn ${activeTab === "SENSORS" ? "btn-primary" : "btn-secondary"}`}
        >
          <Radio size={15} />
          Sensor Nodes ({sensors.length})
        </button>
        <button
          onClick={() => setActiveTab("SOURCES")}
          className={`btn ${activeTab === "SOURCES" ? "btn-primary" : "btn-secondary"}`}
        >
          <Database size={15} />
          Data Sources & Provenance ({sources.length})
        </button>
      </div>

      {activeTab === "SENSORS" ? (
        /* Sensor Nodes Grid */
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 18 }}>
          {sensors.map((sn) => {
            const r = sn.latest_reading;
            return (
              <div key={sn.id} className="card" style={{ marginBottom: 0 }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                      {sn.node_id}
                    </h3>
                    <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>
                      Zone #{sn.zone_id} | {sn.sensor_type}
                    </div>
                  </div>
                  <StaleIndicator isStale={sn.is_stale} lastSeenAt={sn.last_seen_at} />
                </div>

                {/* Latest Telemetry Values */}
                <div style={{
                  background: "rgba(0, 0, 0, 0.25)",
                  padding: 12,
                  borderRadius: 6,
                  border: "1px solid var(--border-subtle)",
                  marginBottom: 12,
                }}>
                  {r ? (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12 }}>
                      <div>
                        <span style={{ color: "var(--text-muted)" }}>Rainfall (1h):</span>
                        <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--accent)" }}>
                          {r.rainfall_1h_mm !== null ? `${r.rainfall_1h_mm} mm` : "—"}
                        </div>
                      </div>

                      <div>
                        <span style={{ color: "var(--text-muted)" }}>Water Level:</span>
                        <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                          {r.water_level_m !== null ? `${r.water_level_m} m` : "—"}
                        </div>
                      </div>

                      <div>
                        <span style={{ color: "var(--text-muted)" }}>Soil Moisture:</span>
                        <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                          {r.soil_moisture_pct !== null ? `${r.soil_moisture_pct}%` : "—"}
                        </div>
                      </div>

                      <div>
                        <span style={{ color: "var(--text-muted)" }}>Temperature:</span>
                        <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                          {r.temperature_c !== null ? `${r.temperature_c} °C` : "—"}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ textAlign: "center", color: "var(--text-dim)", fontSize: 12 }}>
                      No recent telemetry received.
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <DataTrustBadge origin={sn.data_origin} />
                  <button
                    onClick={() => openSensorReadings(sn.node_id)}
                    className="btn btn-secondary btn-sm"
                  >
                    <History size={12} />
                    History
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Data Sources View */
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Provider</th>
                <th>Stale Threshold</th>
                <th>Provenance Notes</th>
                <th>Data Origin</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((ds) => (
                <tr key={ds.id}>
                  <td style={{ fontFamily: "var(--font-mono)" }}>#{ds.id}</td>
                  <td style={{ fontWeight: 600 }}>{ds.name}</td>
                  <td>
                    <span className="badge" style={{ background: "rgba(255,255,255,0.06)" }}>
                      {ds.source_type}
                    </span>
                  </td>
                  <td>{ds.provider || "—"}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>
                    {ds.stale_after_minutes ? `${ds.stale_after_minutes} min` : "Config default"}
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)", maxWidth: 300 }}>
                    {ds.provenance_notes || ds.description || "—"}
                  </td>
                  <td><DataTrustBadge origin={ds.data_origin} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sensor Readings Time-Series Modal */}
      {selectedSensor && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 760 }}>
            <div className="modal-header">
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                Telemetry Log — Node: {selectedSensor}
              </div>
              <button onClick={() => setSelectedSensor(null)} className="btn btn-secondary btn-sm" style={{ padding: 4 }}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body" style={{ maxHeight: "65vh" }}>
              {readingsLoading ? (
                <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted)" }}>
                  Loading time-series...
                </div>
              ) : readings.length === 0 ? (
                <div style={{ textAlign: "center", padding: 30, color: "var(--text-muted)" }}>
                  No historical readings found.
                </div>
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Timestamp (IST)</th>
                        <th>Rain (mm)</th>
                        <th>Water (m)</th>
                        <th>Rate (m/h)</th>
                        <th>Soil (%)</th>
                        <th>Temp (°C)</th>
                        <th>Quality</th>
                      </tr>
                    </thead>
                    <tbody>
                      {readings.map((r) => (
                        <tr key={r.id}>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
                            {new Date(r.observed_at).toLocaleString("en-IN", { hour12: false })}
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)", color: "var(--accent)" }}>
                            {r.rainfall_1h_mm ?? "—"}
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{r.water_level_m ?? "—"}</td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{r.water_level_rate_m_per_h ?? "—"}</td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{r.soil_moisture_pct ?? "—"}</td>
                          <td style={{ fontFamily: "var(--font-mono)" }}>{r.temperature_c ?? "—"}</td>
                          <td>
                            <span className={`badge ${r.quality_status === 'VALID' ? 'badge-active' : 'badge-stale'}`} style={{ fontSize: 10 }}>
                              {r.quality_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button onClick={() => setSelectedSensor(null)} className="btn btn-secondary btn-sm">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sensors;
