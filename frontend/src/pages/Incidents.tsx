import React, { useState, useEffect } from "react";
import {
  Plus,
  Filter,
  X,
  Send,
} from "lucide-react";
import apiClient from "../api/client";
import RiskBadge from "../components/RiskBadge";
import DataTrustBadge from "../components/DataTrustBadge";

export const Incidents: React.FC = () => {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");

  // Modals & Details
  const [selectedIncident, setSelectedIncident] = useState<any>(null);
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [isAddActionOpen, setIsAddActionOpen] = useState<boolean>(false);

  // New Incident Form State
  const [newZoneId, setNewZoneId] = useState<number>(1);
  const [newType, setNewType] = useState<string>("FLOOD");
  const [newSeverity, setNewSeverity] = useState<string>("HIGH");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newLat, setNewLat] = useState<string>("31.712");
  const [newLon, setNewLon] = useState<string>("76.932");

  // New Action Form State
  const [newActionType, setNewActionType] = useState<string>("EVACUATION_ASSISTANCE");
  const [newActionPriority, setNewActionPriority] = useState<string>("HIGH");
  const [newActionNotes, setNewActionNotes] = useState<string>("");

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (severityFilter) params.severity = severityFilter;
      if (typeFilter) params.incident_type = typeFilter;
      const res = await apiClient.get("/incidents", { params });
      setIncidents(res.data.items || []);
    } catch (err) {
      console.error("Failed to fetch incidents", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [statusFilter, severityFilter, typeFilter]);

  const openIncidentDetail = async (id: number) => {
    try {
      const res = await apiClient.get(`/incidents/${id}`);
      setSelectedIncident(res.data);
    } catch (err) {
      alert("Failed to load incident detail");
    }
  };

  const handleCreateIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.post("/incidents", {
        zone_id: Number(newZoneId),
        incident_type: newType,
        severity: newSeverity,
        description: newDesc,
        latitude: newLat ? parseFloat(newLat) : undefined,
        longitude: newLon ? parseFloat(newLon) : undefined,
        data_origin: "SIMULATED",
      });
      setIsCreateOpen(false);
      setNewDesc("");
      fetchIncidents();
    } catch (err: any) {
      alert("Error creating incident: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleAddResponseAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIncident) return;

    try {
      await apiClient.post(`/incidents/${selectedIncident.id}/response-actions`, {
        action_type: newActionType,
        priority: newActionPriority,
        notes: newActionNotes,
      });
      setIsAddActionOpen(false);
      setNewActionNotes("");
      openIncidentDetail(selectedIncident.id);
    } catch (err: any) {
      alert("Error adding action: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpdateIncidentStatus = async (newStatus: string) => {
    if (!selectedIncident) return;
    try {
      const res = await apiClient.patch(`/incidents/${selectedIncident.id}`, {
        status: newStatus,
      });
      setSelectedIncident(res.data);
      fetchIncidents();
    } catch (err: any) {
      alert("Failed to update status: " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Incident Management & Dispatch</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Field incident reporting, verification, and coordinated response actions
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin="SIMULATED" />
          <button onClick={() => setIsCreateOpen(true)} className="btn btn-primary btn-sm">
            <Plus size={14} />
            Report Incident
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ padding: 14, marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: 13 }}>
            <Filter size={14} /> Filter:
          </div>

          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: 140, padding: "6px 10px", fontSize: 12 }}
          >
            <option value="">All Statuses</option>
            <option value="OPEN">OPEN</option>
            <option value="IN_PROGRESS">IN_PROGRESS</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>

          <select
            className="form-select"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{ width: 140, padding: "6px 10px", fontSize: 12 }}
          >
            <option value="">All Severities</option>
            <option value="LOW">LOW</option>
            <option value="MODERATE">MODERATE</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>

          <select
            className="form-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{ width: 140, padding: "6px 10px", fontSize: 12 }}
          >
            <option value="">All Types</option>
            <option value="FLOOD">FLOOD</option>
            <option value="LANDSLIDE">LANDSLIDE</option>
            <option value="OTHER">OTHER</option>
          </select>
        </div>
      </div>

      {/* Incidents Table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Incident Type</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Zone</th>
              <th>Started At</th>
              <th>Origin</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--text-muted)" }}>
                  Loading incidents...
                </td>
              </tr>
            ) : incidents.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--text-muted)" }}>
                  No incident records found.
                </td>
              </tr>
            ) : (
              incidents.map((i) => (
                <tr key={i.id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>#{i.id}</td>
                  <td style={{ fontWeight: 600 }}>{i.incident_type}</td>
                  <td><RiskBadge level={i.severity} /></td>
                  <td>
                    <span className={`badge ${i.status === 'RESOLVED' ? 'badge-active' : i.status === 'OPEN' ? 'badge-risk-crit' : 'badge-risk-high'}`}>
                      {i.status}
                    </span>
                  </td>
                  <td>Zone #{i.zone_id}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {i.started_at ? new Date(i.started_at).toLocaleString("en-IN", { hour12: false }) : "—"}
                  </td>
                  <td><DataTrustBadge origin={i.data_origin} /></td>
                  <td>
                    <button onClick={() => openIncidentDetail(i.id)} className="btn btn-secondary btn-sm">
                      Inspect
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Incident Detail Modal */}
      {selectedIncident && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 16 }}>
                  Incident #{selectedIncident.id} — {selectedIncident.incident_type}
                </span>
                <RiskBadge level={selectedIncident.severity} />
              </div>
              <button onClick={() => setSelectedIncident(null)} className="btn btn-secondary btn-sm" style={{ padding: 4 }}>
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Status: </span>
                  <span className="badge badge-active">{selectedIncident.status}</span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {selectedIncident.status !== "IN_PROGRESS" && selectedIncident.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleUpdateIncidentStatus("IN_PROGRESS")}
                      className="btn btn-secondary btn-sm"
                    >
                      Set In Progress
                    </button>
                  )}
                  {selectedIncident.status !== "RESOLVED" && (
                    <button
                      onClick={() => handleUpdateIncidentStatus("RESOLVED")}
                      className="btn btn-primary btn-sm"
                    >
                      Mark Resolved
                    </button>
                  )}
                </div>
              </div>

              <div style={{ background: "rgba(0, 0, 0, 0.25)", padding: 12, borderRadius: 6, marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase", marginBottom: 4 }}>
                  Description / Situation Report
                </div>
                <div style={{ fontSize: 13, color: "var(--text-main)" }}>
                  {selectedIncident.description || "No description logged."}
                </div>
              </div>

              {/* Response Actions */}
              <div style={{ marginTop: 20 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--accent)" }}>
                    Response Actions ({selectedIncident.response_actions?.length || 0})
                  </span>
                  <button onClick={() => setIsAddActionOpen(true)} className="btn btn-secondary btn-sm">
                    <Plus size={12} /> Add Action
                  </button>
                </div>

                {(!selectedIncident.response_actions || selectedIncident.response_actions.length === 0) ? (
                  <div style={{ padding: 14, textAlign: "center", color: "var(--text-muted)", fontSize: 12, background: "rgba(0, 0, 0, 0.15)", borderRadius: 6 }}>
                    No response actions created yet. Click "Add Action" to deploy or dispatch.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {selectedIncident.response_actions.map((act: any) => (
                      <div key={act.id} style={{ background: "rgba(0, 0, 0, 0.25)", padding: 12, borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{act.action_type}</span>
                          <RiskBadge level={act.priority} />
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                          {act.notes || "No notes."}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-dim)" }}>
                          Status: <strong style={{ color: "var(--text-main)" }}>{act.status}</strong> |
                          Assignments: {(act.assignments || []).length} assigned
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setSelectedIncident(null)} className="btn btn-secondary btn-sm">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Report New Incident Modal */}
      {isCreateOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <div style={{ fontWeight: 700, fontSize: 15 }}>Report New Emergency Incident</div>
              <button onClick={() => setIsCreateOpen(false)} className="btn btn-secondary btn-sm" style={{ padding: 4 }}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateIncident}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Zone ID</label>
                  <select
                    className="form-select"
                    value={newZoneId}
                    onChange={(e) => setNewZoneId(Number(e.target.value))}
                  >
                    <option value={1}>1 — Demo Zone - Mandi Town</option>
                    <option value={2}>2 — Demo Zone - Sundernagar</option>
                    <option value={3}>3 — Demo Zone - Jogindernagar</option>
                    <option value={4}>4 — Demo Zone - Karsog Valley</option>
                    <option value={5}>5 — Demo Zone - Pandoh Dam Area</option>
                  </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Incident Type</label>
                    <select className="form-select" value={newType} onChange={(e) => setNewType(e.target.value)}>
                      <option value="FLOOD">FLOOD</option>
                      <option value="LANDSLIDE">LANDSLIDE</option>
                      <option value="OTHER">OTHER</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Severity</label>
                    <select className="form-select" value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)}>
                      <option value="LOW">LOW</option>
                      <option value="MODERATE">MODERATE</option>
                      <option value="HIGH">HIGH</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Situation Description</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    required
                    placeholder="Describe field conditions, water level, blocked roads..."
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Latitude</label>
                    <input
                      type="text"
                      className="form-input"
                      value={newLat}
                      onChange={(e) => setNewLat(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Longitude</label>
                    <input
                      type="text"
                      className="form-input"
                      value={newLon}
                      onChange={(e) => setNewLon(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setIsCreateOpen(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  <Send size={13} />
                  Submit Incident
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Response Action Modal */}
      {isAddActionOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <div style={{ fontWeight: 700, fontSize: 15 }}>Create Response Action</div>
              <button onClick={() => setIsAddActionOpen(false)} className="btn btn-secondary btn-sm" style={{ padding: 4 }}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleAddResponseAction}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Action Type</label>
                  <select
                    className="form-select"
                    value={newActionType}
                    onChange={(e) => setNewActionType(e.target.value)}
                  >
                    <option value="EVACUATION_ASSISTANCE">EVACUATION_ASSISTANCE</option>
                    <option value="SEARCH_AND_RESCUE">SEARCH_AND_RESCUE</option>
                    <option value="MEDICAL_DISPATCH">MEDICAL_DISPATCH</option>
                    <option value="ROAD_CLEARANCE">ROAD_CLEARANCE</option>
                    <option value="FLOOD_BARRIER_DEPLOYMENT">FLOOD_BARRIER_DEPLOYMENT</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Priority</label>
                  <select
                    className="form-select"
                    value={newActionPriority}
                    onChange={(e) => setNewActionPriority(e.target.value)}
                  >
                    <option value="LOW">LOW</option>
                    <option value="MODERATE">MODERATE</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Operational Notes</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="Instructions for deployed personnel..."
                    value={newActionNotes}
                    onChange={(e) => setNewActionNotes(e.target.value)}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setIsAddActionOpen(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Action
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Incidents;
