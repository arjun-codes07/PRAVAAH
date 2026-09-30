import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Waves, Shield, Lock, UserCheck, AlertCircle, ArrowRight } from "lucide-react";
import apiClient from "../api/client";
import { useAuth } from "../context/AuthContext";
import DataTrustBadge from "../components/DataTrustBadge";

export const Login: React.FC = () => {
  const [email, setEmail] = useState("officer@demo.pravaah.local");
  const [password, setPassword] = useState("DemoOfficer123!");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await apiClient.post("/auth/login", {
        email,
        password,
      });
      await login(res.data.access_token, remember);
      navigate("/");
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Unable to connect to PRAVAAH Command Center. Ensure backend is active.");
      }
    } finally {
      setLoading(false);
    }
  };

  const setPersona = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 20,
      background: "radial-gradient(ellipse at 50% 30%, #162238 0%, #0a0e17 80%)",
    }}>
      <div style={{
        width: "100%",
        maxWidth: 440,
        background: "var(--bg-surface)",
        border: "1px solid var(--border-subtle)",
        borderRadius: 12,
        boxShadow: "0 25px 60px rgba(0, 0, 0, 0.6)",
        overflow: "hidden",
      }}>
        <div style={{
          padding: "32px 32px 24px",
          textAlign: "center",
          borderBottom: "1px solid var(--border-subtle)",
          background: "linear-gradient(180deg, rgba(0, 210, 255, 0.06), transparent)",
        }}>
          <div style={{
            display: "inline-flex",
            padding: 12,
            background: "rgba(0, 210, 255, 0.1)",
            borderRadius: "50%",
            color: "var(--accent)",
            marginBottom: 16,
            boxShadow: "0 0 20px rgba(0, 210, 255, 0.2)",
          }}>
            <Waves size={36} />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "0.08em", color: "var(--accent)" }}>
            PRAVAAH
          </h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
            Hydro-Meteorological Disaster Warning & Response
          </p>
          <div style={{ marginTop: 12 }}>
            <DataTrustBadge origin="SIMULATED" />
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: "28px 32px" }}>
          {error && (
            <div style={{
              background: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#fca5a5",
              borderRadius: 6,
              padding: "10px 14px",
              marginBottom: 20,
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Command Email / Service ID</label>
            <div style={{ position: "relative" }}>
              <input
                type="email"
                className="form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="officer@demo.pravaah.local"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Access Token / Password</label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••••••"
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-muted)", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                style={{ accentColor: "var(--accent)" }}
              />
              Persist session
            </label>
            <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
              HS256 ENCRYPTED
            </span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: "100%", padding: "12px", fontSize: 14 }}
          >
            {loading ? "Authenticating..." : (
              <>
                Initialize Command Session <ArrowRight size={16} />
              </>
            )}
          </button>

          {/* Seed User Quick Select */}
          <div style={{ marginTop: 28, paddingTop: 20, borderTop: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 10, textAlign: "center" }}>
              Quick Demo Personas
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ justifyContent: "flex-start", fontSize: 11 }}
                onClick={() => setPersona("officer@demo.pravaah.local", "DemoOfficer123!")}
              >
                <Shield size={12} style={{ color: "var(--accent)" }} />
                District Officer (District Disaster Authority)
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ justifyContent: "flex-start", fontSize: 11 }}
                onClick={() => setPersona("commander@demo.pravaah.local", "DemoCommander123!")}
              >
                <UserCheck size={12} style={{ color: "var(--risk-high)" }} />
                Incident Commander (Operations & Dispatch)
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ justifyContent: "flex-start", fontSize: 11 }}
                onClick={() => setPersona("coordinator@demo.pravaah.local", "DemoCoordinator123!")}
              >
                <Lock size={12} style={{ color: "var(--risk-mod)" }} />
                Resource Coordinator (Field Units & Teams)
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
