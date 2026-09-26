import L from "leaflet";
import "leaflet.markercluster";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import type { MapIssuePoint, MapSitePoint, MapWorkPoint } from "../api/types";
import { CATEGORY_LABELS } from "../api/types";
import "./wardmap.css";

const PUNE_CENTER: [number, number] = [18.5204, 73.8567];

function categoryColor(category: string | null): string {
  const root = getComputedStyle(document.documentElement);
  const value = root.getPropertyValue(`--cat-${category ?? "other"}`).trim();
  return value || root.getPropertyValue("--cat-other").trim() || "#8a8371";
}

function IssueLayer({
  issues,
  onIssueClick,
  audience,
}: {
  issues: MapIssuePoint[];
  onIssueClick?: (id: number) => void;
  audience: "citizen" | "admin";
}) {
  const map = useMap();
  useEffect(() => {
    const layer = L.layerGroup();
    for (const issue of issues) {
      const priority = issue.priority_score ?? 0;
      // Marker size still reflects priority visually in both audiences -
      // that's a spatial signal, not the raw score. The *number* and the
      // word "evidence" are admin-only; the citizen popup stays plain.
      const radius = 5 + priority * 6;
      const color = categoryColor(issue.category);
      const marker = L.circleMarker([issue.location.lat, issue.location.lon], {
        radius,
        color: "var(--paper-raised)",
        weight: 1.5,
        fillColor: color,
        fillOpacity: 0.85,
        className: "map-marker map-marker--issue",
      });
      const precisionLabel = issue.location_precision === "ward_level" ? "Ward-level location" : "Precise location";
      const popupBody =
        audience === "admin"
          ? `<strong>Issue #${issue.issue_id}</strong><br/>` +
            `${CATEGORY_LABELS[issue.category] ?? issue.category} · ${issue.status}<br/>` +
            `Priority ${priority.toFixed(2)} · ${precisionLabel}` +
            `${onIssueClick ? `<br/><button class="map-popup__link" data-issue="${issue.issue_id}">View evidence →</button>` : ""}`
          : `<strong>${CATEGORY_LABELS[issue.category] ?? issue.category}</strong><br/>` +
            `${issue.status} · ${precisionLabel}` +
            `${onIssueClick ? `<br/><button class="map-popup__link" data-issue="${issue.issue_id}">View details →</button>` : ""}`;
      marker.bindPopup(`<div class="map-popup">${popupBody}</div>`);
      if (onIssueClick) {
        marker.on("popupopen", () => {
          const btn = document.querySelector(`[data-issue="${issue.issue_id}"]`);
          btn?.addEventListener("click", () => onIssueClick(issue.issue_id));
        });
      }
      layer.addLayer(marker);
    }
    layer.addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, issues, onIssueClick, audience]);
  return null;
}

function WorkLayer({ works, onWorkClick }: { works: MapWorkPoint[]; onWorkClick?: (id: number) => void }) {
  const map = useMap();
  useEffect(() => {
    const layer = L.layerGroup();
    for (const work of works) {
      const icon = L.divIcon({
        className: "map-marker map-marker--work",
        html: `<span class="map-marker__diamond" aria-hidden="true"></span>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });
      const marker = L.marker([work.location.lat, work.location.lon], { icon });
      const precisionLabel = work.location_precision === "ward_level" ? "Ward-level location" : "Precise location";
      marker.bindPopup(
        `<div class="map-popup"><strong>Public work #${work.work_id}</strong><br/>${work.work_name}<br/>` +
          `${precisionLabel}` +
          `${onWorkClick ? `<br/><button class="map-popup__link" data-work="${work.work_id}">View record →</button>` : ""}</div>`
      );
      if (onWorkClick) {
        marker.on("popupopen", () => {
          const btn = document.querySelector(`[data-work="${work.work_id}"]`);
          btn?.addEventListener("click", () => onWorkClick(work.work_id));
        });
      }
      layer.addLayer(marker);
    }
    layer.addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, works, onWorkClick]);
  return null;
}

function SiteLayer({ sites }: { sites: MapSitePoint[] }) {
  const map = useMap();
  useEffect(() => {
    // 861 sensitive sites is too dense to render unclustered - this is the
    // one layer where clustering/aggregation is genuinely required.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const clusterGroup = (L as any).markerClusterGroup({
      maxClusterRadius: 45,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      iconCreateFunction: (cluster: any) =>
        L.divIcon({
          html: `<div>${cluster.getChildCount()}</div>`,
          className: "marker-cluster-civic",
          iconSize: L.point(32, 32),
        }),
    });
    for (const site of sites) {
      const marker = L.circleMarker([site.location.lat, site.location.lon], {
        radius: 4,
        color: "var(--ink-faint)",
        weight: 1,
        fillColor: "var(--ink-faint)",
        fillOpacity: 0.5,
      });
      // GET /api/map's MapSitePoint has no `name` field, though the
      // sensitive_sites table does - reported as a gap, not invented.
      marker.bindPopup(`<div class="map-popup">${site.kind}</div>`);
      clusterGroup.addLayer(marker);
    }
    map.addLayer(clusterGroup);
    return () => {
      map.removeLayer(clusterGroup);
    };
  }, [map, sites]);
  return null;
}

export interface WardMapProps {
  issues?: MapIssuePoint[];
  works?: MapWorkPoint[];
  sites?: MapSitePoint[];
  onIssueClick?: (id: number) => void;
  onWorkClick?: (id: number) => void;
  height?: string;
  center?: [number, number];
  zoom?: number;
  focusMarker?: { lat: number; lon: number; label: string };
  /** Controls what an issue popup reveals - "citizen" (default) never shows
   * a raw priority number or the word "evidence"; only admin callers should
   * opt into "admin". Defaults to the safer, more restricted option. */
  audience?: "citizen" | "admin";
}

export function WardMap({
  issues = [],
  works = [],
  sites = [],
  onIssueClick,
  onWorkClick,
  height = "480px",
  center,
  zoom = 12,
  focusMarker,
  audience = "citizen",
}: WardMapProps) {
  const mapCenter = useMemo<[number, number]>(
    () => center ?? (focusMarker ? [focusMarker.lat, focusMarker.lon] : PUNE_CENTER),
    [center, focusMarker]
  );

  return (
    <div className="ward-map" style={{ height }}>
      <MapContainer center={mapCenter} zoom={zoom} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        {/* CartoDB Positron (originally used for a low-chroma basemap) now
            requires an API key for this usage and rendered a watermark
            instead of tiles - found visually, not in any log. Standard OSM
            tiles + a CSS filter get the same muted, non-busy look for free. */}
        <TileLayer
          className="ward-map__tiles"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {sites.length > 0 && <SiteLayer sites={sites} />}
        {works.length > 0 && <WorkLayer works={works} onWorkClick={onWorkClick} />}
        {issues.length > 0 && <IssueLayer issues={issues} onIssueClick={onIssueClick} audience={audience} />}
        {focusMarker && <FocusMarker {...focusMarker} />}
      </MapContainer>
    </div>
  );
}

function FocusMarker({ lat, lon, label }: { lat: number; lon: number; label: string }) {
  const map = useMap();
  useEffect(() => {
    const icon = L.divIcon({
      className: "map-marker map-marker--focus",
      html: `<span class="map-marker__ring" aria-hidden="true"></span>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });
    const marker = L.marker([lat, lon], { icon }).bindPopup(label);
    marker.addTo(map);
    return () => {
      map.removeLayer(marker);
    };
  }, [map, lat, lon, label]);
  return null;
}
