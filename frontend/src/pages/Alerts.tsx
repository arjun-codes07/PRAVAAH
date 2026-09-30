import React, { useState, useEffect } from "react";
import {
  Plus,
  Filter,
  CheckCircle,
  X,
  Send,
} from "lucide-react";
import apiClient from "../api/client";
import RiskBadge from "../components/RiskBadge";
import DataTrustBadge from "../components/DataTrustBadge";

export const Alerts: React.FC = () => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");

  // Issue Alert Modal
  const [isIssueOpen, setIsIssueOpen] = useState<boolean>(false);
  const [newZoneId, setNewZoneId] = useState<number>(1);
  const [newType, setNewType] = useState<string>("FLOOD");
  const [newSeverity, setNewSeverity] = useState<string>("HIGH");
  const [newMessage, setNewMessage] = useState<string>("");
  const [newExpiryHours, setNewExpiryHours] = useState<number>(6);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (severityFilter) params.severity = severityFilter;
      if (typeFilter) params.alert_type = typeFilter;
      const res = await apiClient.get("/alerts", { params });
      setAlerts(res.data.items || []);
    } catch (err) {
      console.error("Failed to fetch alerts", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [statusFilter, severityFilter, typeFilter]);

  const handleAcknowledge = async (id: number) => {
    try {
      await apiClient.post(`/alerts/${id}/acknowledge`);
      fetchAlerts();
    } catch (err: any) {
      alert("Failed to acknowledge: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleIssueAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const expiresAt = new Date(Date.now() + newExpiryHours * 3600 * 1000).toISOString();
      await apiClient.post("/alerts", {
        zone_id: Number(newZoneId),
        alert_type: newType,
        severity: newSeverity,
        message: newMessage,
        expires_at: expiresAt,
        data_origin: "SIMULATED",
      });
      setIsIssueOpen(false);
      setNewMessage("");
      fetchAlerts();
    } catch (err: any) {
      alert("Failed to issue alert: " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Emergency Alerts & Public Warning Feed</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Disaster warning issuance, acknowledgment status, and auditable alert lifecycle
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <DataTrustBadge origin="SIMULATED" />
          <button onClick={() => setIsIssueOpen(true)} className="btn btn-danger btn-sm">
            <Plus size={14} />
            Issue Emergency Alert
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
            style={{ width: 160, padding: "6px 10px", fontSize: 12 }}
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            <option value="CANCELLED">CANCELLED</option>
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

      {/* Alerts Table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Effective Status</th>
              <th>Message</th>
              <th>Zone</th>
              <th>Issued At</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--text-muted)" }}>
                  Loading alerts...
                </td>
              </tr>
            ) : alerts.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--text-muted)" }}>
                  No alerts currently match the criteria.
                </td>
              </tr>
            ) : (
              alerts.map((alt) => {
                const isEffectiveActive = alt.effective_status === "ACTIVE" || alt.status === "ACTIVE";
                return (
                  <tr key={alt.id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>#{alt.id}</td>
                    <td style={{ fontWeight: 600 }}>{alt.alert_type}</td>
                    <td><RiskBadge level={alt.severity} /></td>
                    <td>
                      <span className={`badge ${isEffectiveActive ? 'badge-risk-crit' : 'badge-active'}`}>
                        {alt.effective_status || alt.status}
                      </span>
                    </td>
                    <td style={{ maxWidth: 360, color: "var(--text-main)" }}>
                      {alt.message}
                    </td>
                    <td>Zone #{alt.zone_id}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {new Date(alt.issued_at).toLocaleString("en-IN", { hour12: false })}
                    </td>
                    <td>
                      {alt.status === "ACTIVE" ? (
                        <button onClick={() => handleAcknowledge(alt.id)} className="btn btn-primary btn-sm">
                          <CheckCircle size={12} /> Acknowledge
                        </button>
                      ) : (
                        <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                          Acknowledged
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Issue Alert Modal */}
      {isIssueOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <div style={{ fontWeight: 700, fontSize: 15 }}>Issue District Emergency Warning</div>
              <button onClick={() => setIsIssueOpen(false)} className="btn btn-secondary btn-sm" style={{ padding: 4 }}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleIssueAlert}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Zone</label>
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
                    <label className="form-label">Hazard Type</label>
                    <select className="form-select" value={newType} onChange={(e) => setNewType(e.target.value)}>
                      <option value="FLOOD">FLOOD</option>
                      <option value="LANDSLIDE">LANDSLIDE</option>
                      <option value="OTHER">OTHER</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Severity Level</label>
                    <select className="form-select" value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)}>
                      <option value="MODERATE">MODERATE</option>
                      <option value="HIGH">HIGH</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Emergency Broadcast Message</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    required
                    placeholder="E.g. Warning: Rapidly rising river levels near Mandi Beas bridge. Avoid low-lying riverbanks."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Alert Duration (Hours)</label>
                  <select
                    className="form-select"
                    value={newExpiryHours}
                    onChange={(e) => setNewExpiryHours(Number(e.target.value))}
                  >
                    <option value={2}>2 hours</option>
                    <option value={6}>6 hours</option>
                    <option value={12}>12 hours</option>
                    <option value={24}>24 hours</option>
                  </select>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setIsIssueOpen(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-danger">
                  <Send size={13} />
                  Issue Alert (Audited)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Alerts;
