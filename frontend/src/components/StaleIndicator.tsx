import React from "react";
import { Radio, AlertOctagon } from "lucide-react";

interface Props {
  isStale: boolean;
  lastSeenAt?: string | null;
}

export const StaleIndicator: React.FC<Props> = ({ isStale, lastSeenAt }) => {
  const formattedTime = lastSeenAt
    ? new Date(lastSeenAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "Never";

  if (isStale) {
    return (
      <span className="badge badge-stale" title={`No data received recently. Last seen: ${formattedTime}`}>
        <AlertOctagon size={12} />
        STALE ({formattedTime})
      </span>
    );
  }

  return (
    <span className="badge badge-active" title={`Active telemetry. Last seen: ${formattedTime}`}>
      <Radio size={12} />
      ONLINE ({formattedTime})
    </span>
  );
};

export default StaleIndicator;
