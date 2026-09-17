import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { PlaceFeature } from "./types";
import { Protocol } from "pmtiles";

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const STYLE =
  import.meta.env.VITE_MAP_STYLE ??
  "https://z.yuiseki.net/static/maps/styles/osm-fiord.json";

interface Props {
  features: PlaceFeature[];
}

/** The map. Only places that resolved to an OSM entity have coordinates, so
 * only those are drawn; a misheard place name is absent rather than plotted
 * somewhere plausible but wrong. */
export function MapView({ features }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!holder.current || map.current) return;
    // MapLibre needs WebGL, which is absent on plenty of machines people
    // actually use: virtual desktops, remote sessions, containers without a
    // GPU. Letting the constructor throw takes the whole page down with it,
    // including the chart and the candidate list, which do not need a GPU at
    // all. Keep those working and say what happened instead.
    let m: maplibregl.Map;
    try {
      m = new maplibregl.Map({
        container: holder.current,
        style: STYLE,
        center: [138, 37],
        zoom: 4,
        attributionControl: { compact: true },
      });
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
      return;
    }
    m.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    m.on("load", () => {
      m.addSource("places", { type: "geojson", data: empty() });
      m.addLayer({
        id: "places-circle",
        type: "circle",
        source: "places",
        paint: {
          "circle-radius": 6,
          // Same rose as a candidate on the chart: a marker and the point
          // that led you to it are the same finding.
          "circle-color": paletteColor("--hot", "#f43f5e"),
          "circle-stroke-width": 1.5,
          "circle-stroke-color": paletteColor("--bg", "#0f172a"),
        },
      });
      m.on("click", "places-circle", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as Record<string, string>;
        new maplibregl.Popup({ closeButton: true })
          .setLngLat(
            (f.geometry as GeoJSON.Point).coordinates as [number, number],
          )
          .setHTML(
            `<strong>${escapeHtml(p.mention ?? "")}</strong><br>` +
              `${escapeHtml(p.display_name ?? "")}<br>` +
              `<small>${escapeHtml(p.t ?? "")}</small>`,
          )
          .addTo(m);
      });
      m.on(
        "mouseenter",
        "places-circle",
        () => (m.getCanvas().style.cursor = "pointer"),
      );
      m.on(
        "mouseleave",
        "places-circle",
        () => (m.getCanvas().style.cursor = ""),
      );
      setReady(true);
    });
    map.current = m;
    return () => {
      setReady(false);
      m.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    // Waiting on `ready` rather than on a load event registered from here:
    // React runs effects twice in development, and a listener attached to the
    // first map instance never fires once that instance has been thrown away,
    // which left the second map with no data and no fitBounds.
    {
      const src = m.getSource("places") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      // A place with no coordinates is dropped here rather than earlier, so
      // that the counts in the panel still include it. GeoJSON permits a null
      // geometry; a map layer does not.
      const data: GeoJSON.FeatureCollection<GeoJSON.Point> = {
        type: "FeatureCollection",
        features: features.flatMap((f) =>
          f.geometry
            ? [
                {
                  type: "Feature" as const,
                  geometry: f.geometry,
                  properties: { ...f.properties },
                },
              ]
            : [],
        ),
      };
      src.setData(data);
      const coords = data.features.map((f) => f.geometry.coordinates as Point);
      if (coords.length === 0) return;
      const main = dominantCluster(coords);
      // The container is absolutely positioned, so on the first pass the map
      // can still have no size and fitBounds would compute against zero.
      m.resize();
      const padding = overlayPadding(m.getContainer());
      if (main.length === 1) {
        m.easeTo({ center: main[0], zoom: 8, padding, duration: 600 });
        return;
      }
      const b = main.reduce(
        (acc, c) => acc.extend(c),
        new maplibregl.LngLatBounds(main[0], main[0]),
      );
      m.fitBounds(b, { padding, maxZoom: 10, duration: 600 });
    }
  }, [features, ready]);

  if (failed) {
    return (
      <div className="nomap">
        <p>The map needs WebGL, and this browser could not provide it.</p>
        <p className="muted small">{failed}</p>
        <p className="muted small">
          The time series and the candidate list below do not need it and still
          work.
        </p>
      </div>
    );
  }

  return <div ref={holder} style={{ position: "absolute", inset: 0 }} />;
}

/** Padding that keeps the markers out from under the overlays.
 *
 * Measured rather than hard-coded: the panel's height depends on how many
 * candidates there are, and the chart's on how wide the window is. A uniform
 * padding puts half the markers behind the panel.
 *
 * Clamped to a third of the map on each axis, because MapLibre throws if the
 * padding leaves no room, and a very small window legitimately has none.
 */
function overlayPadding(container: HTMLElement) {
  const map = container.getBoundingClientRect();
  const gap = 16;
  const box = (selector: string) => document.querySelector(selector)?.getBoundingClientRect();
  const panel = box(".panel");
  const chart = box(".chart");
  const clampX = (v: number) => Math.max(24, Math.min(v, map.width / 3));
  const clampY = (v: number) => Math.max(24, Math.min(v, map.height / 3));
  return {
    top: clampY(gap),
    right: clampX(gap),
    left: clampX(panel ? panel.right - map.left + gap : gap),
    bottom: clampY(chart ? map.bottom - chart.top + gap : gap),
  };
}

/** Degrees within which two places count as the same cluster. Three is about
 * 300km at these latitudes: loose enough to hold a prefecture and its
 * neighbours together, tight enough to keep Kumamoto and Colombia apart. */
const CLUSTER_DEG = 3;

type Point = [number, number];

function spread(cluster: Point[]): number {
  const lons = cluster.map((p) => p[0]);
  const lats = cluster.map((p) => p[1]);
  return (
    Math.max(...lons) - Math.min(...lons) + (Math.max(...lats) - Math.min(...lats))
  );
}

/** The biggest group of places that are near each other.
 *
 * All the markers are drawn; this only decides where to point the camera. On a
 * day with an earthquake in Kumamoto there is usually also foreign disaster
 * news, and fitting the bounds to everything zooms out until the thing that
 * made the day unusual is three pixels wide. Ties go to the tighter cluster,
 * because two groups of equal size are better represented by the denser one.
 *
 * Greedy single-linkage: a point joins a cluster if it is near any member.
 * Good enough for tens of points and easy to reason about, which matters more
 * here than the clustering being optimal.
 */
function dominantCluster(points: Point[]): Point[] {
  if (points.length <= 1) return points;
  const clusters: Point[][] = [];
  for (const p of points) {
    const near = clusters.find((c) =>
      c.some((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) <= CLUSTER_DEG),
    );
    if (near) near.push(p);
    else clusters.push([p]);
  }
  clusters.sort((a, b) => b.length - a.length || spread(a) - spread(b));
  return clusters[0] ?? points;
}

function paletteColor(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function empty(): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

function escapeHtml(s: string) {
  return s.replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ] ?? c,
  );
}
