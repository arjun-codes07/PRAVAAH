import React from "react";
import { ShieldAlert, RefreshCw, CheckCircle } from "lucide-react";

interface Props {
  origin: "REAL" | "SIMULATED" | "REPLAYED" | string;
  size?: "sm" | "md";
}

export const DataTrustBadge: React.FC<Props> = ({ origin }) => {
  if (origin === "SIMULATED") {
    return (
      <span className="badge badge-origin-sim" title="Simulated synthetic data generated for system verification">
        <ShieldAlert size={12} />
        SIMULATED
      </span>
    );
  }

  if (origin === "REPLAYED") {
    return (
      <span className="badge badge-origin-rep" title="Historical sensor data replayed through ingestion stream">
        <RefreshCw size={12} />
        REPLAYED
      </span>
    );
  }

  return (
    <span className="badge badge-origin-real" title="Live operational field telemetry">
      <CheckCircle size={12} />
      REAL
    </span>
  );
};

export default DataTrustBadge;
