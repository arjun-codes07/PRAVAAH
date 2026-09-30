import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Waves,
  LayoutDashboard,
  Map as MapIcon,
  ShieldAlert,
  AlertTriangle,
  Bell,
  Truck,
  Activity,
  LogOut,
  Clock,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }) + " IST"
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { label: "Dashboard", path: "/", icon: <LayoutDashboard size={15} /> },
    { label: "Map View", path: "/map", icon: <MapIcon size={15} /> },
    { label: "Zones & Risk", path: "/zones", icon: <ShieldAlert size={15} /> },
    { label: "Incidents", path: "/incidents", icon: <AlertTriangle size={15} /> },
    { label: "Alerts", path: "/alerts", icon: <Bell size={15} /> },
    { label: "Response", path: "/response", icon: <Truck size={15} /> },
    { label: "Sensors & Data", path: "/sensors", icon: <Activity size={15} /> },
  ];

  return (
    <header className="navbar">
      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <Link to="/" className="nav-brand">
          <Waves size={22} />
          PRAVAAH
          <span>CRISIS COMMAND</span>
        </Link>

        <nav className="nav-links">
          {navItems.map((item) => {
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-link ${isActive ? "active" : ""}`}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="nav-user">
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)", fontSize: 12, fontFamily: "var(--font-mono)" }}>
          <Clock size={13} style={{ color: "var(--accent)" }} />
          {timeStr}
        </div>

        {user && (
          <div className="nav-user-info">
            <div className="nav-user-name">{user.name}</div>
            <div className="nav-user-role">{user.role}</div>
          </div>
        )}

        <button
          onClick={logout}
          className="btn btn-secondary btn-sm"
          title="Sign out of command session"
        >
          <LogOut size={14} />
          Exit
        </button>
      </div>
    </header>
  );
};

export default Navbar;
