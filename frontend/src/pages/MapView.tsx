import React, { useEffect, useRef, useState, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { 
  Layers, 
  RefreshCw, 
  Maximize2, 
  RotateCcw, 
  Activity, 
  ShieldAlert, 
  Radio, 
  Map as MapIcon,
  CheckCircle2,
  Info,
  Ambulance,
  Route as RouteIcon,
  Navigation
} from "lucide-react";
import apiClient from "../api/client";
import DataTrustBadge from "../components/DataTrustBadge";

// Configure MapLibre Web Worker URL via Vite's worker pipeline
maplibregl.setWorkerUrl(workerUrl);

// MapTiler style identifiers
const MAPTILER_STYLES: Record<string, { label: string; id: string }> = {
  hybrid: { label: "Satellite Hybrid (Aerial + Roads)", id: "hybrid" },
  topo: { label: "Topographic (Elevation / Contours)", id: "topo-v2" },
  dataviz: { label: "DataViz Dark (Tactical Vector)", id: "dataviz-dark" },
  streets: { label: "Dark Streets", id: "streets-v2-dark" },
};

// Fallback CARTO Dark raster style when no MapTiler API key is provided
const FALLBACK_CARTO_DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "carto-dark": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors &copy; <a href=\"https://carto.com/attributions\">CARTO</a>",
    },
  },
  layers: [
    {
      id: "carto-dark-base",
      type: "raster",
      source: "carto-dark",
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

const MANDI_CENTER: [number, number] = [76.93, 31.71]; // [lon, lat] Mandi District, HP
const DEFAULT_ZOOM = 10.5;
const DEFAULT_PITCH = 25;

export const MapView: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const featuresRef = useRef<any>(null);

  const [features, setFeatures] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Map settings state
  const mapTilerKey = (import.meta.env.VITE_MAPTILER_API_KEY || "").trim();
  const [selectedStyleKey, setSelectedStyleKey] = useState<string>("hybrid");
  const [minRiskFilter, setMinRiskFilter] = useState<string>("");

  // Spatial layer visibility toggles
  const [showZones, setShowZones] = useState<boolean>(true);
  const [showZoneLabels, setShowZoneLabels] = useState<boolean>(true);
  const [showEvacZones, setShowEvacZones] = useState<boolean>(true);
  const [showSensors, setShowSensors] = useState<boolean>(true);
  const [showIncidents, setShowIncidents] = useState<boolean>(true);
  const [showTeams, setShowTeams] = useState<boolean>(true);
  const [showRescueRoutes, setShowRescueRoutes] = useState<boolean>(true);
  const [showEvacRoutes, setShowEvacRoutes] = useState<boolean>(true);

  // Quick stats from loaded features
  const [stats, setStats] = useState({
    zones: 0,
    sensors: 0,
    incidents: 0,
    teams: 0,
    resources: 0,
    evacZones: 0,
    rescueRoutes: 0,
    evacRoutes: 0,
    criticalZones: 0,
  });

  // Keep featuresRef in sync for style.load callbacks
  useEffect(() => {
    featuresRef.current = features;
  }, [features]);

  // Determine current style spec / URL
  const getStyleUrlOrSpec = useCallback((styleKey: string) => {
    if (mapTilerKey) {
      const styleId = MAPTILER_STYLES[styleKey]?.id || "hybrid";
      return `https://api.maptiler.com/maps/${styleId}/style.json?key=${mapTilerKey}`;
    }
    return FALLBACK_CARTO_DARK_STYLE;
  }, [mapTilerKey]);

  // Helper to get risk level hex color (consistent across application)
  const getRiskColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case "CRITICAL": return "#ef4444";
      case "HIGH": return "#f97316";
      case "MEDIUM":
      case "MODERATE": return "#f59e0b";
      case "LOW":
      default: return "#22c55e";
    }
  };

  // Fetch geographic data from PRAVAAH API
  const fetchFeatures = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        layers: "zones,incidents,sensors,resources,teams,rescue_routes,evacuation_zones,evacuation_routes",
      };
      if (minRiskFilter) {
        params.min_level = minRiskFilter;
      }
      const res = await apiClient.get("/map/features", { params });
      console.log("[PRAVAAH Map] Fetched features:", res.data?.features?.length);
      setFeatures(res.data);
      featuresRef.current = res.data;
      setError(null);

      // Compute stats
      const items = res.data?.features || [];
      let zCount = 0;
      let sCount = 0;
      let iCount = 0;
      let tCount = 0;
      let rCount = 0;
      let ezCount = 0;
      let rrCount = 0;
      let erCount = 0;
      let critCount = 0;

      items.forEach((f: any) => {
        const layer = (f.properties?.layer || f.properties?.entity_type || "").toLowerCase();
        if (layer === "zones") {
          zCount++;
          if (f.properties?.overall_risk_level?.toUpperCase() === "CRITICAL") {
            critCount++;
          }
        } else if (layer === "sensors") {
          sCount++;
        } else if (layer === "incidents") {
          iCount++;
        } else if (layer === "teams") {
          tCount++;
        } else if (layer === "resources") {
          rCount++;
        } else if (layer === "evacuation_zones") {
          ezCount++;
        } else if (layer === "rescue_routes") {
          rrCount++;
        } else if (layer === "evacuation_routes") {
          erCount++;
        }
      });

      setStats({
        zones: zCount,
        sensors: sCount,
        incidents: iCount,
        teams: tCount,
        resources: rCount,
        evacZones: ezCount,
        rescueRoutes: rrCount,
        evacRoutes: erCount,
        criticalZones: critCount,
      });
    } catch {
      setError("Failed to load GIS spatial features from backend API.");
    } finally {
      setLoading(false);
    }
  }, [minRiskFilter]);

  // Initial data fetch
  useEffect(() => {
    fetchFeatures();
  }, [fetchFeatures]);

  // Setup click popups and hover cursors on all interactive layers
  const setupInteractions = useCallback((map: maplibregl.Map) => {
    const interactiveLayers = [
      { id: "pravaah-zones-fill", type: "zone" },
      { id: "pravaah-evac-zones-fill", type: "evac_zone" },
      { id: "pravaah-sensors-circle", type: "sensor" },
      { id: "pravaah-incidents-circle", type: "incident" },
      { id: "pravaah-teams-circle", type: "team" },
      { id: "pravaah-resources-circle", type: "resource" },
      { id: "pravaah-rescue-routes-line", type: "rescue_route" },
      { id: "pravaah-evac-routes-line", type: "evac_route" },
    ];

    interactiveLayers.forEach(({ id, type }) => {
      if (!map.getLayer(id)) return;

      // Cursor hover
      map.on("mouseenter", id, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", id, () => {
        map.getCanvas().style.cursor = "";
      });

      // Click handler
      map.on("click", id, (e) => {
        if (!e.features || e.features.length === 0) return;
        const feature = e.features[0];
        const p = feature.properties || {};

        if (popupRef.current) {
          popupRef.current.remove();
        }

        let popupContent = "";

        if (type === "zone") {
          const riskColor = getRiskColor(p.overall_risk_level);
          const zoneId = p.zone_id || p.id;
          popupContent = `
            <div style="font-family: inherit; min-width: 250px; line-height: 1.45;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #00d2ff; font-weight: 700;">
                  PRAVAAH RISK ZONE
                </span>
                <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.4); border: 1px solid ${riskColor}; color: ${riskColor}; font-weight: 800;">
                  ${p.overall_risk_level || "LOW"} RISK
                </span>
              </div>
              <div style="font-weight: 700; font-size: 15px; color: #ffffff; margin-bottom: 6px;">
                ${p.name || "Monitored Basin"}
              </div>
              <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px; margin-bottom: 10px; font-size: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="color: #9ca3af;">Risk Score:</span>
                  <strong style="color: ${riskColor};">${p.risk_score !== undefined ? p.risk_score : "N/A"} / 4.0</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="color: #9ca3af;">Primary Hazard:</span>
                  <strong style="color: #f3f4f6;">${p.primary_hazard || "Multi-Hazard"}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="color: #9ca3af;">Flood / Landslide:</span>
                  <span style="color: #e5e7eb;">${p.flood_risk_level || "LOW"} / ${p.landslide_risk_level || "LOW"}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span style="color: #9ca3af;">Forecast Horizon:</span>
                  <span style="color: #e5e7eb;">${p.horizon_minutes || 60} mins</span>
                </div>
              </div>
              ${p.recommended_action ? `
                <div style="font-size: 11px; color: #d1d5db; background: rgba(239, 68, 68, 0.08); border-left: 2px solid ${riskColor}; padding: 6px 8px; margin-bottom: 10px;">
                  <strong>Advisory:</strong> ${p.recommended_action}
                </div>
              ` : ""}
              <a href="/zones/${zoneId}" style="display: block; text-align: center; font-size: 12px; font-weight: 600; color: #00d2ff; text-decoration: none; padding: 7px 10px; background: rgba(0, 210, 255, 0.12); border: 1px solid rgba(0, 210, 255, 0.35); border-radius: 4px;">
                Open Zone Intelligence &rarr;
              </a>
            </div>
          `;
        } else if (type === "evac_zone") {
          popupContent = `
            <div style="font-family: inherit; min-width: 230px; line-height: 1.45;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; text-transform: uppercase; color: #60a5fa; font-weight: 700;">
                  EVACUATION ZONE
                </span>
                <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: rgba(37, 99, 235, 0.2); border: 1px solid #3b82f6; color: #93c5fd; font-weight: 700;">
                  ${p.evac_code || "EV-01"}
                </span>
              </div>
              <div style="font-weight: 700; font-size: 14px; color: #ffffff; margin-bottom: 6px;">
                ${p.name || "Civic Assembly Center"}
              </div>
              <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 6px; padding: 8px; margin-bottom: 10px; font-size: 12px;">
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Facility Type: <strong style="color: #f3f4f6;">${p.shelter_type || "Civic Building"}</strong>
                </div>
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Operational Status: <strong style="color: #34d399;">${p.status || "ACTIVE_SHELTER"}</strong>
                </div>
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Related Risk Zone: <span style="color: #f3f4f6;">${p.related_zone_name || "Mandi"}</span>
                </div>
                <div style="color: #6b7280; font-size: 11px;">
                  ${p.capacity || "Designated safe assembly location"}
                </div>
              </div>
              <div style="font-size: 11px; color: #60a5fa; text-align: center; padding: 4px; background: rgba(59, 130, 246, 0.1); border-radius: 4px;">
                Designated Safe Shelter Zone
              </div>
            </div>
          `;
        } else if (type === "sensor") {
          const condition = p.sensor_condition || (p.is_stale ? "WARNING" : "NORMAL");
          let condColor = "#22c55e";
          if (condition === "CRITICAL") condColor = "#ef4444";
          else if (condition === "ELEVATED") condColor = "#f97316";
          else if (condition === "WARNING") condColor = "#f59e0b";

          popupContent = `
            <div style="font-family: inherit; min-width: 230px; line-height: 1.45;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; text-transform: uppercase; color: #00d2ff; font-weight: 700;">
                  TELEMETRY SENSOR
                </span>
                <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${condColor}22; border: 1px solid ${condColor}55; color: ${condColor}; font-weight: 700;">
                  ${condition}
                </span>
              </div>
              <div style="font-weight: 700; font-size: 14px; color: #ffffff; margin-bottom: 4px;">
                ${p.node_id || "Sensor Station"}
              </div>
              <div style="font-size: 11px; color: #9ca3af; margin-bottom: 8px;">
                Location: <span style="color: #e5e7eb;">${p.zone_name || "Mandi Urban"}</span> &bull; ${p.sensor_type || "MULTI_SENSOR"}
              </div>
              <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px; margin-bottom: 10px; font-size: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="color: #9ca3af;">River Water Level:</span>
                  <strong style="color: ${p.water_level_m >= 3.5 ? '#ef4444' : '#f3f4f6'};">${p.water_level_m !== null && p.water_level_m !== undefined ? p.water_level_m + ' m' : 'N/A'}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="color: #9ca3af;">Rainfall Rate (1h):</span>
                  <strong style="color: ${p.rainfall_1h_mm >= 30.0 ? '#ef4444' : '#f3f4f6'};">${p.rainfall_1h_mm !== null && p.rainfall_1h_mm !== undefined ? p.rainfall_1h_mm + ' mm' : 'N/A'}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="color: #9ca3af;">Soil Saturation:</span>
                  <span style="color: #f3f4f6;">${p.soil_moisture_pct !== null && p.soil_moisture_pct !== undefined ? p.soil_moisture_pct + ' %' : 'N/A'}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span style="color: #9ca3af;">Hardware Link:</span>
                  <span style="color: ${p.is_stale ? '#f59e0b' : '#34d399'}; font-weight: 600;">${p.is_stale ? "STALE TELEMETRY" : "LIVE ONLINE"}</span>
                </div>
              </div>
              <div style="font-size: 10px; color: #6b7280; margin-bottom: 10px;">
                Last Reading: ${p.latest_observed_at ? new Date(p.latest_observed_at).toLocaleTimeString() : (p.last_seen_at ? new Date(p.last_seen_at).toLocaleTimeString() : "Recent")}
              </div>
              <a href="/sensors" style="display: block; text-align: center; font-size: 11px; color: #00d2ff; text-decoration: none; padding: 6px; background: rgba(0, 210, 255, 0.1); border-radius: 4px;">
                Inspect Sensor Stream &rarr;
              </a>
            </div>
          `;
        } else if (type === "incident") {
          const sevColor = getRiskColor(p.severity);
          popupContent = `
            <div style="font-family: inherit; min-width: 230px; line-height: 1.45;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; color: #ef4444; font-weight: 800;">INCIDENT #${p.id}</span>
                <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${sevColor}22; border: 1px solid ${sevColor}55; color: ${sevColor}; font-weight: 700;">
                  ${p.severity || "HIGH"} SEVERITY
                </span>
              </div>
              <div style="font-weight: 700; font-size: 14px; color: #ffffff; margin-bottom: 4px;">
                ${p.type || "Hazard Incident"}
              </div>
              <div style="font-size: 11px; color: #9ca3af; margin-bottom: 6px;">
                Location: <span style="color: #e5e7eb;">${p.zone_name || "Monitored Zone"}</span> &bull; Status: <strong style="color: #f3f4f6;">${p.status || "OPEN"}</strong>
              </div>
              <div style="font-size: 12px; color: #d1d5db; background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.08); border-radius: 4px; padding: 8px; margin-bottom: 10px;">
                ${p.description || "Active emergency incident under coordination."}
              </div>
              <a href="/incidents" style="display: block; text-align: center; font-size: 11px; color: #00d2ff; text-decoration: none; padding: 6px; background: rgba(0, 210, 255, 0.1); border-radius: 4px;">
                Open Incident Management &rarr;
              </a>
            </div>
          `;
        } else if (type === "team") {
          const isDeployed = p.status === "DEPLOYED";
          popupContent = `
            <div style="font-family: inherit; min-width: 230px; line-height: 1.45;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; text-transform: uppercase; color: #3b82f6; font-weight: 700;">
                  RESCUE OPERATION UNIT
                </span>
                <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${isDeployed ? 'rgba(59, 130, 246, 0.2)' : 'rgba(34, 197, 94, 0.2)'}; border: 1px solid ${isDeployed ? '#3b82f6' : '#22c55e'}; color: ${isDeployed ? '#60a5fa' : '#4ade80'}; font-weight: 700;">
                  ${p.status || "AVAILABLE"}
                </span>
              </div>
              <div style="font-weight: 700; font-size: 14px; color: #ffffff; margin-bottom: 4px;">
                ${p.name || "Rescue Team"}
              </div>
              <div style="font-size: 11px; color: #9ca3af; margin-bottom: 8px;">
                Classification: <strong style="color: #e5e7eb;">${p.team_type || "NDRF"}</strong>
              </div>
              <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 6px; padding: 8px; margin-bottom: 10px; font-size: 12px;">
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Assigned Incident: <strong style="color: #f3f4f6;">${p.assigned_incident_id ? `Incident #${p.assigned_incident_id} (${p.assigned_incident_type})` : "Unassigned (Standby)"}</strong>
                </div>
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Action Plan: <span style="color: #60a5fa;">${p.assigned_action_type || "Standby Readiness"}</span>
                </div>
                <div style="color: #9ca3af;">
                  Operational Base / Scene: <span style="color: #f3f4f6;">${p.destination_name || "Command Center"}</span>
                </div>
              </div>
              <a href="/response" style="display: block; text-align: center; font-size: 11px; color: #60a5fa; text-decoration: none; padding: 6px; background: rgba(59, 130, 246, 0.12); border-radius: 4px;">
                Response Fleet Details &rarr;
              </a>
            </div>
          `;
        } else if (type === "resource") {
          popupContent = `
            <div style="font-family: inherit; min-width: 200px; line-height: 1.45;">
              <div style="font-size: 11px; text-transform: uppercase; color: #a78bfa; font-weight: 700; margin-bottom: 2px;">
                RESCUE RESOURCE ASSET
              </div>
              <div style="font-weight: 700; font-size: 13px; color: #ffffff; margin-bottom: 4px;">
                ${p.name || "Equipment Unit"}
              </div>
              <div style="font-size: 12px; color: #9ca3af; margin-bottom: 4px;">
                Type: <strong style="color: #f3f4f6;">${p.type || "EQUIPMENT"}</strong> (Qty: ${p.quantity || 1})
              </div>
              <div style="font-size: 12px; color: #9ca3af; margin-bottom: 8px;">
                Status: <strong style="color: ${p.status === "AVAILABLE" ? "#22c55e" : "#a78bfa"};">${p.status || "AVAILABLE"}</strong>
              </div>
              <div style="font-size: 11px; color: #6b7280; margin-bottom: 8px;">
                Attached Team: ${p.team_name || "Independent Reserve"}
              </div>
              <a href="/response" style="display: block; text-align: center; font-size: 11px; color: #a78bfa; text-decoration: none; padding: 5px; background: rgba(139, 92, 246, 0.1); border-radius: 4px;">
                Inventory View &rarr;
              </a>
            </div>
          `;
        } else if (type === "rescue_route") {
          popupContent = `
            <div style="font-family: inherit; min-width: 240px; line-height: 1.45;">
              <div style="font-size: 11px; text-transform: uppercase; color: #38bdf8; font-weight: 700; margin-bottom: 2px;">
                ACTIVE RESCUE DEPLOYMENT ROUTE
              </div>
              <div style="font-weight: 700; font-size: 13px; color: #ffffff; margin-bottom: 6px;">
                ${p.team_name || "Rescue Team"} &rarr; Scene
              </div>
              <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 6px; padding: 8px; margin-bottom: 8px; font-size: 12px;">
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Incident Destination: <strong style="color: #ef4444;">#${p.incident_id} (${p.incident_type})</strong>
                </div>
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Target Zone: <span style="color: #f3f4f6;">${p.destination || "Mandi"}</span>
                </div>
                <div style="color: #9ca3af;">
                  Unit Status: <strong style="color: #38bdf8;">${p.team_status || "DEPLOYED"}</strong>
                </div>
              </div>
              <div style="font-size: 11px; color: #38bdf8; text-align: center; padding: 4px; background: rgba(56, 189, 248, 0.1); border-radius: 4px;">
                Direct Deployment Vector (Live Mission)
              </div>
            </div>
          `;
        } else if (type === "evac_route") {
          popupContent = `
            <div style="font-family: inherit; min-width: 240px; line-height: 1.45;">
              <div style="font-size: 11px; text-transform: uppercase; color: #06b6d4; font-weight: 700; margin-bottom: 2px;">
                DESIGNATED PUBLIC EVACUATION CORRIDOR
              </div>
              <div style="font-weight: 700; font-size: 13px; color: #ffffff; margin-bottom: 6px;">
                Hazard Zone &rarr; Safe Shelter
              </div>
              <div style="background: rgba(0,0,0,0.35); border: 1px solid rgba(6, 182, 212, 0.35); border-radius: 6px; padding: 8px; margin-bottom: 8px; font-size: 12px;">
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  From Hazard: <strong style="color: #f97316;">${p.incident_type || "Flood Hazard"}</strong>
                </div>
                <div style="margin-bottom: 4px; color: #9ca3af;">
                  Designated Shelter: <strong style="color: #34d399;">${p.shelter_name || "Emergency Shelter"}</strong>
                </div>
                <div style="color: #9ca3af;">
                  Corridor Status: <span style="color: #06b6d4; font-weight: 600;">OPEN FOR CIVIC TRANSIT</span>
                </div>
              </div>
              <div style="font-size: 11px; color: #06b6d4; text-align: center; padding: 4px; background: rgba(6, 182, 212, 0.1); border-radius: 4px;">
                Official Evacuation Transit Path
              </div>
            </div>
          `;
        }

        const coordinates = (e.lngLat ? [e.lngLat.lng, e.lngLat.lat] : MANDI_CENTER) as [number, number];

        const popup = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          maxWidth: "320px",
          offset: 12,
        })
          .setLngLat(coordinates)
          .setHTML(popupContent)
          .addTo(map);

        popupRef.current = popup;
      });
    });
  }, []);

  // Safe function to add or restore all custom PRAVAAH GeoJSON sources and WebGL layers
  const addPravaahOperationalLayers = useCallback((map: maplibregl.Map, geojson: any) => {
    if (!map || !geojson || !map.isStyleLoaded()) return;

    const allFeatures = geojson.features || [];
    console.log("[PRAVAAH Map] Adding/Updating operational layers with features count:", allFeatures.length);

    // Filter features into respective collections
    const zonesData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || f.properties?.entity_type || "").toLowerCase();
        return l === "zones" || l === "zone";
      }),
    };

    const evacZonesData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || "").toLowerCase();
        return l === "evacuation_zones" || l === "evac_zones";
      }),
    };

    const sensorsData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || f.properties?.entity_type || "").toLowerCase();
        return l === "sensors" || l === "sensor";
      }),
    };

    const incidentsData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || f.properties?.entity_type || "").toLowerCase();
        return l === "incidents" || l === "incident";
      }),
    };

    const teamsData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || "").toLowerCase();
        return l === "teams" || l === "team";
      }),
    };

    const resourcesData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || f.properties?.entity_type || "").toLowerCase();
        return l === "resources" || l === "resource";
      }),
    };

    const rescueRoutesData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || "").toLowerCase();
        return l === "rescue_routes" || l === "rescue_route";
      }),
    };

    const evacRoutesData = {
      type: "FeatureCollection",
      features: allFeatures.filter((f: any) => {
        const l = (f.properties?.layer || "").toLowerCase();
        return l === "evacuation_routes" || l === "evac_routes";
      }),
    };

    // Helper to safely set or create GeoJSON source
    const updateOrCreateSource = (srcId: string, data: any) => {
      const src = map.getSource(srcId) as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(data);
        return true;
      }
      map.addSource(srcId, { type: "geojson", data });
      return false;
    };

    // 1. RISK ZONES (Bottom polygon layer)
    updateOrCreateSource("pravaah-zones", zonesData);
    if (!map.getLayer("pravaah-zones-fill")) {
      map.addLayer({
        id: "pravaah-zones-fill",
        type: "fill",
        source: "pravaah-zones",
        paint: {
          "fill-color": [
            "match",
            ["upcase", ["coalesce", ["get", "overall_risk_level"], "LOW"]],
            "CRITICAL", "rgba(239, 68, 68, 0.40)",
            "HIGH", "rgba(249, 115, 22, 0.40)",
            "MEDIUM", "rgba(245, 158, 11, 0.40)",
            "MODERATE", "rgba(245, 158, 11, 0.40)",
            "LOW", "rgba(34, 197, 94, 0.30)",
            "rgba(34, 197, 94, 0.30)",
          ],
          "fill-opacity": 0.85,
        },
      });
    }

    if (!map.getLayer("pravaah-zones-outline")) {
      map.addLayer({
        id: "pravaah-zones-outline",
        type: "line",
        source: "pravaah-zones",
        paint: {
          "line-color": [
            "match",
            ["upcase", ["coalesce", ["get", "overall_risk_level"], "LOW"]],
            "CRITICAL", "#ef4444",
            "HIGH", "#f97316",
            "MEDIUM", "#f59e0b",
            "MODERATE", "#f59e0b",
            "LOW", "#22c55e",
            "#22c55e",
          ],
          "line-width": 3,
          "line-opacity": 0.95,
        },
      });
    }

    if (!map.getLayer("pravaah-zones-labels")) {
      map.addLayer({
        id: "pravaah-zones-labels",
        type: "symbol",
        source: "pravaah-zones",
        layout: {
          "text-field": [
            "concat",
            ["get", "name"],
            "\n",
            ["get", "overall_risk_level"],
            " RISK (",
            ["to-string", ["get", "risk_score"]],
            ")"
          ],
          "text-size": 11.5,
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#ffffff",
          "text-halo-color": "#0a0e17",
          "text-halo-width": 2.5,
        },
      });
    }

    // 2. EVACUATION ZONES (Blue semi-transparent polygon layer)
    updateOrCreateSource("pravaah-evac-zones", evacZonesData);
    if (!map.getLayer("pravaah-evac-zones-fill")) {
      map.addLayer({
        id: "pravaah-evac-zones-fill",
        type: "fill",
        source: "pravaah-evac-zones",
        paint: {
          "fill-color": "rgba(37, 99, 235, 0.35)",
          "fill-opacity": 0.85,
        },
      });
    }

    if (!map.getLayer("pravaah-evac-zones-outline")) {
      map.addLayer({
        id: "pravaah-evac-zones-outline",
        type: "line",
        source: "pravaah-evac-zones",
        paint: {
          "line-color": "#3b82f6",
          "line-width": 2.5,
          "line-opacity": 0.95,
        },
      });
    }

    if (!map.getLayer("pravaah-evac-zones-labels")) {
      map.addLayer({
        id: "pravaah-evac-zones-labels",
        type: "symbol",
        source: "pravaah-evac-zones",
        layout: {
          "text-field": ["concat", "EVAC: ", ["get", "evac_code"], "\n", ["get", "name"]],
          "text-size": 10.5,
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#93c5fd",
          "text-halo-color": "#0f172a",
          "text-halo-width": 2,
        },
      });
    }

    // 3. EVACUATION ROUTES (Cyan solid line for public transit)
    updateOrCreateSource("pravaah-evac-routes", evacRoutesData);
    if (!map.getLayer("pravaah-evac-routes-casing")) {
      map.addLayer({
        id: "pravaah-evac-routes-casing",
        type: "line",
        source: "pravaah-evac-routes",
        paint: {
          "line-color": "#083344",
          "line-width": 6,
          "line-opacity": 0.7,
        },
      });
    }

    if (!map.getLayer("pravaah-evac-routes-line")) {
      map.addLayer({
        id: "pravaah-evac-routes-line",
        type: "line",
        source: "pravaah-evac-routes",
        paint: {
          "line-color": "#06b6d4",
          "line-width": 3.8,
          "line-opacity": 0.95,
        },
      });
    }

    // 4. RESCUE ROUTES (Sky blue dashed line for active rescue operations)
    updateOrCreateSource("pravaah-rescue-routes", rescueRoutesData);
    if (!map.getLayer("pravaah-rescue-routes-casing")) {
      map.addLayer({
        id: "pravaah-rescue-routes-casing",
        type: "line",
        source: "pravaah-rescue-routes",
        paint: {
          "line-color": "#0f172a",
          "line-width": 6,
          "line-opacity": 0.7,
        },
      });
    }

    if (!map.getLayer("pravaah-rescue-routes-line")) {
      map.addLayer({
        id: "pravaah-rescue-routes-line",
        type: "line",
        source: "pravaah-rescue-routes",
        paint: {
          "line-color": "#38bdf8",
          "line-width": 3.8,
          "line-dasharray": [3, 2],
          "line-opacity": 1.0,
        },
      });
    }

    // 5. SENSORS (Status color coded)
    updateOrCreateSource("pravaah-sensors", sensorsData);
    if (!map.getLayer("pravaah-sensors-halo")) {
      map.addLayer({
        id: "pravaah-sensors-halo",
        type: "circle",
        source: "pravaah-sensors",
        paint: {
          "circle-radius": 13,
          "circle-color": [
            "match",
            ["coalesce", ["get", "sensor_condition"], "NORMAL"],
            "CRITICAL", "#ef4444",
            "ELEVATED", "#f97316",
            "WARNING", "#f59e0b",
            "#22c55e"
          ],
          "circle-opacity": 0.35,
        },
      });
    }

    if (!map.getLayer("pravaah-sensors-circle")) {
      map.addLayer({
        id: "pravaah-sensors-circle",
        type: "circle",
        source: "pravaah-sensors",
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "match",
            ["coalesce", ["get", "sensor_condition"], "NORMAL"],
            "CRITICAL", "#ef4444",
            "ELEVATED", "#f97316",
            "WARNING", "#f59e0b",
            "#22c55e"
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
    }

    // 6. INCIDENTS (Severity color coded with warning halos)
    updateOrCreateSource("pravaah-incidents", incidentsData);
    if (!map.getLayer("pravaah-incidents-halo")) {
      map.addLayer({
        id: "pravaah-incidents-halo",
        type: "circle",
        source: "pravaah-incidents",
        paint: {
          "circle-radius": 17,
          "circle-color": [
            "match",
            ["upcase", ["coalesce", ["get", "severity"], "HIGH"]],
            "CRITICAL", "#ef4444",
            "HIGH", "#f97316",
            "MEDIUM", "#f59e0b",
            "MODERATE", "#f59e0b",
            "#22c55e"
          ],
          "circle-opacity": 0.4,
        },
      });
    }

    if (!map.getLayer("pravaah-incidents-circle")) {
      map.addLayer({
        id: "pravaah-incidents-circle",
        type: "circle",
        source: "pravaah-incidents",
        paint: {
          "circle-radius": 9.5,
          "circle-color": [
            "match",
            ["upcase", ["coalesce", ["get", "severity"], "HIGH"]],
            "CRITICAL", "#ef4444",
            "HIGH", "#f97316",
            "MEDIUM", "#f59e0b",
            "MODERATE", "#f59e0b",
            "#22c55e"
          ],
          "circle-stroke-width": 2.5,
          "circle-stroke-color": "#ffffff",
        },
      });
    }

    // 7. RESCUE TEAMS (Distinct blue rescue units)
    updateOrCreateSource("pravaah-teams", teamsData);
    if (!map.getLayer("pravaah-teams-halo")) {
      map.addLayer({
        id: "pravaah-teams-halo",
        type: "circle",
        source: "pravaah-teams",
        paint: {
          "circle-radius": 15,
          "circle-color": "#3b82f6",
          "circle-opacity": 0.4,
        },
      });
    }

    if (!map.getLayer("pravaah-teams-circle")) {
      map.addLayer({
        id: "pravaah-teams-circle",
        type: "circle",
        source: "pravaah-teams",
        paint: {
          "circle-radius": 9,
          "circle-color": "#2563eb",
          "circle-stroke-width": 2.5,
          "circle-stroke-color": "#60a5fa",
        },
      });
    }

    // 8. RESCUE RESOURCES
    updateOrCreateSource("pravaah-resources", resourcesData);
    if (!map.getLayer("pravaah-resources-circle")) {
      map.addLayer({
        id: "pravaah-resources-circle",
        type: "circle",
        source: "pravaah-resources",
        paint: {
          "circle-radius": 7,
          "circle-color": "#8b5cf6",
          "circle-stroke-width": 1.8,
          "circle-stroke-color": "#ffffff",
        },
      });
    }

    // Attach click and hover events to layers
    setupInteractions(map);
  }, [setupInteractions]);

  // Initialize MapLibre GL Map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const initialStyle = getStyleUrlOrSpec(selectedStyleKey);

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: initialStyle,
      center: MANDI_CENTER,
      zoom: DEFAULT_ZOOM,
      pitch: DEFAULT_PITCH,
      attributionControl: false,
    });

    // Error diagnostics
    map.on("error", (e) => {
      console.error("[PRAVAAH MapLibre Error]", e?.error || e);
    });

    // Navigation Controls
    map.addControl(
      new maplibregl.NavigationControl({
        visualizePitch: true,
        showCompass: true,
      }),
      "top-right"
    );

    map.addControl(new maplibregl.FullscreenControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");

    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "PRAVAAH Disaster Decision Support System",
      }),
      "bottom-right"
    );

    map.on("load", () => {
      console.log("[PRAVAAH Map] Map load event fired. Ready for overlays.");
      if (featuresRef.current) {
        addPravaahOperationalLayers(map, featuresRef.current);
      }
    });

    // Style Change Safety: restore all layers whenever any basemap style finishes loading
    map.on("style.load", () => {
      console.log("[PRAVAAH Map] Style load event fired. Restoring overlays.");
      if (featuresRef.current) {
        addPravaahOperationalLayers(map, featuresRef.current);
      }
    });

    mapRef.current = map;

    // ResizeObserver to handle container layout changes
    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) {
        mapRef.current.resize();
      }
    });
    resizeObserver.observe(mapContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      if (popupRef.current) {
        popupRef.current.remove();
      }
      map.remove();
      mapRef.current = null;
    };
  }, [getStyleUrlOrSpec, selectedStyleKey, addPravaahOperationalLayers]);

  // Synchronize features whenever they change or arrive from API
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !features) return;

    if (map.isStyleLoaded()) {
      addPravaahOperationalLayers(map, features);
    } else {
      map.once("style.load", () => {
        addPravaahOperationalLayers(map, features);
      });
    }
  }, [features, addPravaahOperationalLayers]);

  // Handle layer visibility toggles via MapLibre layout properties
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const setVis = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    };

    // Risk Zones
    setVis("pravaah-zones-fill", showZones);
    setVis("pravaah-zones-outline", showZones);
    setVis("pravaah-zones-labels", showZoneLabels && showZones);

    // Evacuation Zones
    setVis("pravaah-evac-zones-fill", showEvacZones);
    setVis("pravaah-evac-zones-outline", showEvacZones);
    setVis("pravaah-evac-zones-labels", showEvacZones);

    // Routes
    setVis("pravaah-evac-routes-casing", showEvacRoutes);
    setVis("pravaah-evac-routes-line", showEvacRoutes);
    setVis("pravaah-rescue-routes-casing", showRescueRoutes);
    setVis("pravaah-rescue-routes-line", showRescueRoutes);

    // Point Markers
    setVis("pravaah-sensors-halo", showSensors);
    setVis("pravaah-sensors-circle", showSensors);
    setVis("pravaah-incidents-halo", showIncidents);
    setVis("pravaah-incidents-circle", showIncidents);
    setVis("pravaah-teams-halo", showTeams);
    setVis("pravaah-teams-circle", showTeams);
    setVis("pravaah-resources-circle", showTeams);
  }, [
    showZones, 
    showZoneLabels, 
    showEvacZones, 
    showSensors, 
    showIncidents, 
    showTeams, 
    showRescueRoutes, 
    showEvacRoutes
  ]);

  // Handle Base Map Style Switcher
  const handleStyleChange = (newStyleKey: string) => {
    setSelectedStyleKey(newStyleKey);
    const map = mapRef.current;
    if (!map) return;

    const newStyle = getStyleUrlOrSpec(newStyleKey);
    map.setStyle(newStyle);
  };

  // Fit bounds to all loaded features across all layers
  const fitToData = () => {
    const map = mapRef.current;
    if (!map || !features || !features.features || features.features.length === 0) return;

    const bounds = new maplibregl.LngLatBounds();
    let count = 0;

    const extendCoords = (coords: any) => {
      if (typeof coords[0] === "number" && typeof coords[1] === "number") {
        bounds.extend(coords as [number, number]);
        count++;
      } else if (Array.isArray(coords)) {
        coords.forEach(extendCoords);
      }
    };

    features.features.forEach((f: any) => {
      if (f.geometry && f.geometry.coordinates) {
        extendCoords(f.geometry.coordinates);
      }
    });

    if (count > 0) {
      map.fitBounds(bounds, {
        padding: 80,
        maxZoom: 13.5,
        duration: 1000,
      });
    }
  };

  // Reset view to Mandi Center
  const resetView = () => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({
      center: MANDI_CENTER,
      zoom: DEFAULT_ZOOM,
      pitch: DEFAULT_PITCH,
      bearing: 0,
      duration: 1000,
    });
  };

  return (
    <div>
      {/* Header bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700 }}>Interactive Disaster & Risk Map</h1>
            <span style={{ fontSize: 11, background: "rgba(0, 210, 255, 0.15)", color: "#00d2ff", border: "1px solid rgba(0, 210, 255, 0.3)", padding: "2px 7px", borderRadius: 4, fontWeight: 600 }}>
              MapLibre GL &bull; WebGL Tactical
            </span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            Real-time multi-hazard risk zones, rescue deployments & evacuation corridors for Himachal Pradesh
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <DataTrustBadge origin="SIMULATED" />
          <button 
            onClick={fetchFeatures} 
            disabled={loading}
            className="btn btn-secondary btn-sm"
            title="Refresh spatial data from API"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            {loading ? "Loading..." : "Refresh"}
          </button>
          <button 
            onClick={fitToData} 
            className="btn btn-secondary btn-sm"
            title="Fit view to all features"
          >
            <Maximize2 size={13} />
            Fit All Data
          </button>
          <button 
            onClick={resetView} 
            className="btn btn-secondary btn-sm"
            title="Reset view to Mandi Basin"
          >
            <RotateCcw size={13} />
            Reset
          </button>
        </div>
      </div>

      {/* MapTiler status notice */}
      {mapTilerKey ? (
        <div style={{ padding: "8px 12px", background: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.25)", borderRadius: 6, marginBottom: 14, display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12, color: "#6ee7b7" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <CheckCircle2 size={14} style={{ color: "#10b981" }} />
            <span>MapTiler Satellite/Vector Base-map active via <code>VITE_MAPTILER_API_KEY</code></span>
          </div>
          <span style={{ fontSize: 11, opacity: 0.85, color: "var(--accent)" }}>
            Current Base: {MAPTILER_STYLES[selectedStyleKey]?.label}
          </span>
        </div>
      ) : (
        <div style={{ padding: "8px 12px", background: "rgba(0, 210, 255, 0.08)", border: "1px solid rgba(0, 210, 255, 0.2)", borderRadius: 6, marginBottom: 14, display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--accent)" }}>
          <Info size={14} />
          <span>Running with high-contrast tactical dark basemap. Add <code>VITE_MAPTILER_API_KEY</code> to <code>frontend/.env</code> for MapTiler Satellite Hybrid & Topographic vectors.</span>
        </div>
      )}

      {error && (
        <div style={{ padding: 12, background: "rgba(239, 68, 68, 0.15)", borderRadius: 6, marginBottom: 14, color: "#fca5a5" }}>
          {error}
        </div>
      )}

      {/* Map Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 310px", gap: 18, alignItems: "start" }}>
        {/* Map Container */}
        <div className="card" style={{ padding: 0, overflow: "hidden", position: "relative", minHeight: "720px" }}>
          <div ref={mapContainerRef} style={{ width: "100%", height: "720px" }} />

          {/* Quick HUD overlay in top-left of map */}
          <div style={{
            position: "absolute",
            top: 12,
            left: 12,
            zIndex: 2,
            background: "rgba(17, 25, 39, 0.88)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(255, 255, 255, 0.14)",
            borderRadius: 6,
            padding: "8px 14px",
            display: "flex",
            gap: 14,
            fontSize: 12,
            pointerEvents: "none",
          }}>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block" }}>RISK ZONES</span>
              <strong>{stats.zones}</strong>
            </div>
            <div style={{ width: 1, background: "var(--border-subtle)" }} />
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block" }}>CRITICAL</span>
              <strong style={{ color: stats.criticalZones > 0 ? "#ef4444" : "#22c55e" }}>{stats.criticalZones}</strong>
            </div>
            <div style={{ width: 1, background: "var(--border-subtle)" }} />
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block" }}>SENSORS</span>
              <strong>{stats.sensors}</strong>
            </div>
            <div style={{ width: 1, background: "var(--border-subtle)" }} />
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block" }}>INCIDENTS</span>
              <strong style={{ color: stats.incidents > 0 ? "#f97316" : "#f3f4f6" }}>{stats.incidents}</strong>
            </div>
            <div style={{ width: 1, background: "var(--border-subtle)" }} />
            <div>
              <span style={{ color: "#60a5fa", fontSize: 10, display: "block" }}>RESCUE TEAMS</span>
              <strong style={{ color: "#60a5fa" }}>{stats.teams}</strong>
            </div>
          </div>
        </div>

        {/* Sidebar Controls */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Base Map Style Switcher */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: 10 }}>
              <div className="card-title" style={{ fontSize: 14 }}>
                <MapIcon size={15} style={{ color: "var(--accent)" }} />
                Base-Map Imagery
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {Object.entries(MAPTILER_STYLES).map(([key, info]) => {
                const isActive = selectedStyleKey === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => handleStyleChange(key)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "7px 10px",
                      borderRadius: 6,
                      fontSize: 12,
                      background: isActive ? "rgba(0, 210, 255, 0.15)" : "rgba(255, 255, 255, 0.03)",
                      border: isActive ? "1px solid #00d2ff" : "1px solid var(--border-subtle)",
                      color: isActive ? "#ffffff" : "var(--text-muted)",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <span>{info.label}</span>
                    {isActive && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00d2ff" }} />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Spatial Layer Toggles */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: 10 }}>
              <div className="card-title" style={{ fontSize: 14 }}>
                <Layers size={15} style={{ color: "var(--accent)" }} />
                Spatial Layers
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {/* Risk Zone Polygons */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 12, height: 12, borderRadius: 2, background: "rgba(239, 68, 68, 0.6)", border: "1px solid #ef4444" }} />
                  <span>Risk Zone Polygons</span>
                </span>
                <input
                  type="checkbox"
                  checked={showZones}
                  onChange={(e) => setShowZones(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Risk Zone Labels */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5, paddingLeft: 20 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--text-muted)" }}>
                  <span>&bull; Zone Name & Score Labels</span>
                </span>
                <input
                  type="checkbox"
                  disabled={!showZones}
                  checked={showZoneLabels}
                  onChange={(e) => setShowZoneLabels(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Evacuation Zones */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 12, height: 12, borderRadius: 2, background: "rgba(37, 99, 235, 0.6)", border: "1px solid #3b82f6" }} />
                  <span>Evacuation Safe Zones</span>
                </span>
                <input
                  type="checkbox"
                  checked={showEvacZones}
                  onChange={(e) => setShowEvacZones(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Rescue Routes */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <RouteIcon size={13} style={{ color: "#38bdf8" }} />
                  <span>Rescue Team Routes</span>
                </span>
                <input
                  type="checkbox"
                  checked={showRescueRoutes}
                  onChange={(e) => setShowRescueRoutes(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Evacuation Routes */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Navigation size={13} style={{ color: "#06b6d4" }} />
                  <span>Evacuation Corridors</span>
                </span>
                <input
                  type="checkbox"
                  checked={showEvacRoutes}
                  onChange={(e) => setShowEvacRoutes(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Telemetry Sensors */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Radio size={13} style={{ color: "#22c55e" }} />
                  <span>Telemetry Sensors</span>
                </span>
                <input
                  type="checkbox"
                  checked={showSensors}
                  onChange={(e) => setShowSensors(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Active Incidents */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ShieldAlert size={13} style={{ color: "#ef4444" }} />
                  <span>Active Incidents</span>
                </span>
                <input
                  type="checkbox"
                  checked={showIncidents}
                  onChange={(e) => setShowIncidents(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>

              {/* Rescue Teams & Resources */}
              <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", fontSize: 12.5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Ambulance size={13} style={{ color: "#3b82f6" }} />
                  <span>Rescue Teams & Units</span>
                </span>
                <input
                  type="checkbox"
                  checked={showTeams}
                  onChange={(e) => setShowTeams(e.target.checked)}
                  style={{ accentColor: "var(--accent)", cursor: "pointer" }}
                />
              </label>
            </div>

            {/* Filter by Risk Level */}
            <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border-subtle)" }}>
              <label style={{ display: "block", fontSize: 11, color: "var(--text-muted)", marginBottom: 5 }}>
                Filter Risk Threshold:
              </label>
              <select
                value={minRiskFilter}
                onChange={(e) => setMinRiskFilter(e.target.value)}
                className="input-field"
                style={{ fontSize: 12, padding: "6px 8px" }}
              >
                <option value="">All Monitored Zones</option>
                <option value="MODERATE">Moderate Risk & Above</option>
                <option value="HIGH">High & Critical Only</option>
                <option value="CRITICAL">Critical Priority Only</option>
              </select>
            </div>
          </div>

          {/* Tactical Legend */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: 10 }}>
              <div className="card-title" style={{ fontSize: 14 }}>
                <Activity size={15} style={{ color: "var(--accent)" }} />
                Tactical Legend
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 7, fontSize: 11.5 }}>
              {/* Risk Levels */}
              <div style={{ fontSize: 10.5, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
                Risk Levels
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 13, height: 13, borderRadius: 2, background: "rgba(239, 68, 68, 0.4)", border: "1.5px solid #ef4444" }} />
                <span>🔴 Critical Risk (&ge; 3.0)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 13, height: 13, borderRadius: 2, background: "rgba(249, 115, 22, 0.4)", border: "1.5px solid #f97316" }} />
                <span>🟠 High Risk (2.0 - 2.99)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 13, height: 13, borderRadius: 2, background: "rgba(245, 158, 11, 0.4)", border: "1.5px solid #f59e0b" }} />
                <span>🟡 Medium Risk (1.0 - 1.99)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 13, height: 13, borderRadius: 2, background: "rgba(34, 197, 94, 0.35)", border: "1.5px solid #22c55e" }} />
                <span>🟢 Low Risk (&lt; 1.0)</span>
              </div>

              <div style={{ height: 1, background: "var(--border-subtle)", margin: "4px 0" }} />

              {/* Operational Assets */}
              <div style={{ fontSize: 10.5, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
                Operational Overlays
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#22c55e", border: "1.5px solid #ffffff" }} />
                <span>Sensor Station (Normal)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b", border: "1.5px solid #ffffff" }} />
                <span>Sensor Station (Warning / Stale)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#ef4444", border: "2px solid #ffffff" }} />
                <span>Active Incident Point</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#2563eb", border: "2px solid #60a5fa" }} />
                <span>Rescue Team (NDRF / SDRF)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 13, height: 13, borderRadius: 2, background: "rgba(37, 99, 235, 0.4)", border: "1.5px solid #3b82f6" }} />
                <span>Evacuation Safe Shelter Zone</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 22, height: 0, borderTop: "2.5px dashed #38bdf8" }} />
                <span>Rescue Route (Blue dashed)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 22, height: 0, borderTop: "2.5px solid #06b6d4" }} />
                <span>Evacuation Corridor (Cyan solid)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapView;
