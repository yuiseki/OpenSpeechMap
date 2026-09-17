import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { COLOUR } from "./palette.js";

maplibregl.addProtocol("pmtiles", new Protocol().tile);

const STYLE =
  import.meta.env.VITE_MAP_STYLE ??
  "https://z.yuiseki.net/static/maps/styles/osm-fiord.json";

/** A map in the element given, and a handle for putting places on it.
 *
 * Drawn by MapLibre. nasa/openmct-map is not used: nothing since 2022, no
 * licence, and a README saying it is not for production. Drawing it ourselves
 * is also what the other Open MCT consoles in dwg7 do — the framework supplies
 * the tree and the chrome, the view supplies its own pixels.
 *
 * Only places that resolved to an OSM entity have coordinates, so only those
 * are drawn. A misheard name is absent rather than plotted somewhere plausible
 * but wrong.
 */
export function createMap(holder) {
  let map;
  // MapLibre needs WebGL, which is absent on plenty of machines people
  // actually use: virtual desktops, remote sessions, containers with no GPU.
  // Letting the constructor throw would take the whole view down with it,
  // including a chart that needs no GPU at all.
  try {
    map = new maplibregl.Map({
      container: holder,
      style: STYLE,
      center: [138, 37],
      zoom: 4,
      attributionControl: { compact: true },
    });
  } catch (e) {
    holder.textContent = `map unavailable: ${e instanceof Error ? e.message : e}`;
    return { setFeatures() {}, destroy() {} };
  }

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

  let pending = null;
  let ready = false;

  map.on("load", () => {
    map.addSource("places", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addLayer({
      id: "places-circle",
      type: "circle",
      source: "places",
      paint: {
        "circle-radius": 6,
        "circle-color": COLOUR.hot,
        "circle-stroke-width": 1.5,
        "circle-stroke-color": COLOUR.bg,
      },
    });
    map.on("click", "places-circle", (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      const p = f.properties || {};
      new maplibregl.Popup({ closeButton: true })
        .setLngLat(f.geometry.coordinates)
        .setHTML(
          `<strong>${escapeHtml(p.mention || "")}</strong><br>` +
            `${escapeHtml(p.display_name || "")}<br>` +
            `<small>${escapeHtml(p.t || "")}</small>`,
        )
        .addTo(map);
    });
    map.on("mouseenter", "places-circle", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "places-circle", () => (map.getCanvas().style.cursor = ""));
    ready = true;
    if (pending) {
      const { features, fit } = pending;
      pending = null;
      apply(features, fit);
    }
  });

  function apply(features, fit) {
    const drawn = features.filter((f) => f.geometry);
    map.getSource("places").setData({ type: "FeatureCollection", features: drawn });
    if (!fit || drawn.length === 0) return;
    const bounds = drawn.reduce(
      (b, f) => b.extend(f.geometry.coordinates),
      new maplibregl.LngLatBounds(drawn[0].geometry.coordinates, drawn[0].geometry.coordinates),
    );
    map.fitBounds(bounds, { padding: 48, maxZoom: 9, duration: 300 });
  }

  return {
    /** Held until the style has loaded. Setting data before then is silently
     * dropped, which is how the first render ends up empty. */
    setFeatures(features, { fit = false } = {}) {
      if (ready) apply(features, fit);
      else pending = { features, fit };
    },
    resize() {
      if (ready) map.resize();
    },
    destroy() {
      map.remove();
    },
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}
