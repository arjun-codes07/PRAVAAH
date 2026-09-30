import React from "react";
import { AlertTriangle } from "lucide-react";

export const PrototypeBanner: React.FC = () => {
  return (
    <div className="prototype-banner">
      <AlertTriangle size={14} />
      <span>Prototype System — Simulated & Demonstration Data — Not for Real-World Emergency Operations</span>
    </div>
  );
};

export default PrototypeBanner;
