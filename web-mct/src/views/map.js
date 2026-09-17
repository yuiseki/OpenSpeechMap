import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { COLOUR } from "../palette.js";
import { get, placesAt } from "../data.js";

maplibregl.addProtocol("pmtiles", new Protocol().tile);

const STYLE =
  import.meta.env.VITE_MAP_STYLE ??
  "https://z.yuiseki.net/static/maps/styles/osm-fiord.json";

/** Where places were named.
 *
 * Drawn by MapLibre into the element Open MCT hands us. nasa/openmct-map is
 * not used: it has not been touched since 2022, carries no licence, and says
 * in its own README that it is not for production. Drawing it ourselves is
 * also what the other Open MCT consoles in dwg7 do — the framework supplies
 * the tree and the chrome, the view supplies its own pixels.
 *
 * Only places that resolved to an OSM entity have coordinates, so only those
 * are drawn. A misheard name is absent rather than plotted somewhere
 * plausible but wrong.
 */
export function mapView() {
  return {
    key: "osm.places",
    name: "Places",
    cssClass: "icon-map",
    canView: (domainObject) => domainObject.type === "osm.places",
    view: (domainObject) => {
      let map = null;
      let holder = null;
      return {
        show(element) {
          holder = document.createElement("div");
          holder.className = "osm-map";
          element.appendChild(holder);

          // MapLibre needs WebGL, which is absent on plenty of machines people
          // actually use: virtual desktops, remote sessions, containers with no
          // GPU. Letting the constructor throw would take the console down with
          // it, including every view that needs no GPU at all.
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
            return;
          }
          map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
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

            get(domainObject.osm.source).then(({ places }) => {
              const features = placesAt(places, null).filter((f) => f.geometry);
              map.getSource("places").setData({ type: "FeatureCollection", features });
              if (features.length === 0) return;
              const bounds = features.reduce(
                (b, f) => b.extend(f.geometry.coordinates),
                new maplibregl.LngLatBounds(
                  features[0].geometry.coordinates,
                  features[0].geometry.coordinates,
                ),
              );
              map.fitBounds(bounds, { padding: 48, maxZoom: 9, duration: 0 });
            });
          });
        },
        destroy() {
          if (map) map.remove();
          map = null;
          holder = null;
        },
      };
    },
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}
