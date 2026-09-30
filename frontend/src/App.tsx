import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import PrototypeBanner from "./components/PrototypeBanner";
import Navbar from "./components/Navbar";

// Pages
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import MapView from "./pages/MapView";
import ZonesList from "./pages/ZonesList";
import ZoneDetail from "./pages/ZoneDetail";
import Incidents from "./pages/Incidents";
import Alerts from "./pages/Alerts";
import Response from "./pages/Response";
import Sensors from "./pages/Sensors";

const ProtectedLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-dark)",
        color: "var(--text-muted)",
      }}>
        Initializing Security Context...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-container">
      <PrototypeBanner />
      <Navbar />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            path="/"
            element={
              <ProtectedLayout>
                <Dashboard />
              </ProtectedLayout>
            }
          />

          <Route
            path="/map"
            element={
              <ProtectedLayout>
                <MapView />
              </ProtectedLayout>
            }
          />

          <Route
            path="/zones"
            element={
              <ProtectedLayout>
                <ZonesList />
              </ProtectedLayout>
            }
          />

          <Route
            path="/zones/:id"
            element={
              <ProtectedLayout>
                <ZoneDetail />
              </ProtectedLayout>
            }
          />

          <Route
            path="/incidents"
            element={
              <ProtectedLayout>
                <Incidents />
              </ProtectedLayout>
            }
          />

          <Route
            path="/alerts"
            element={
              <ProtectedLayout>
                <Alerts />
              </ProtectedLayout>
            }
          />

          <Route
            path="/response"
            element={
              <ProtectedLayout>
                <Response />
              </ProtectedLayout>
            }
          />

          <Route
            path="/sensors"
            element={
              <ProtectedLayout>
                <Sensors />
              </ProtectedLayout>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
};

export default App;
