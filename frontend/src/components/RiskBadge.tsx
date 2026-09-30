import React from "react";
import { ShieldCheck, AlertCircle, AlertTriangle, Flame } from "lucide-react";

interface Props {
  level: "LOW" | "MODERATE" | "HIGH" | "CRITICAL" | string | null | undefined;
}

export const RiskBadge: React.FC<Props> = ({ level }) => {
  const lvl = (level || "LOW").toUpperCase();

  if (lvl === "CRITICAL") {
    return (
      <span className="badge badge-risk-crit">
        <Flame size={12} />
        CRITICAL
      </span>
    );
  }

  if (lvl === "HIGH") {
    return (
      <span className="badge badge-risk-high">
        <AlertTriangle size={12} />
        HIGH
      </span>
    );
  }

  if (lvl === "MODERATE") {
    return (
      <span className="badge badge-risk-mod">
        <AlertCircle size={12} />
        MODERATE
      </span>
    );
  }

  return (
    <span className="badge badge-risk-low">
      <ShieldCheck size={12} />
      LOW
    </span>
  );
};

export default RiskBadge;
