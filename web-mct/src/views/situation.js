import { get, placesAt } from "../data.js";
import { renderChart } from "../chart.js";
import { createMap } from "../mapview.js";

/** One series and the places, in one view, with the chart driving the map.
 *
 * Built as a single custom view that lays out both panes itself, rather than
 * as a Display Layout holding two objects. cafebabe's
 * patterns/open-mct-telemetry.md records that sas0 and m3xx-fleet both reached
 * for Display Layout, found it does not agree with objects that come from a
 * provider, and settled on exactly this: one object, one view, build the panel
 * by hand.
 *
 * The coupling is deliberately local, not through the time conductor. Setting
 * conductor bounds would be the mission-control idiom, but it would also mean
 * a click here silently changes what every other open view is showing. A day
 * picked on this chart is a question about this chart.
 */
export function situationView() {
  return {
    key: "osm.situation",
    name: "Counts and places",
    cssClass: "icon-layers",
    canView: (domainObject) => domainObject.type === "osm.series",
    priority: () => 100, // ahead of the chart-only view in the switcher
    view: (domainObject) => {
      let root = null;
      let map = null;
      let observer = null;
      return {
        show(element) {
          root = document.createElement("div");
          root.className = "osm-split";
          // Map on top, chart under it. The map is what the operator is
          // looking at; the chart is how they choose what the map shows.
          const mapPane = document.createElement("div");
          mapPane.className = "osm-split-map";
          const bar = document.createElement("div");
          bar.className = "osm-split-bar";
          const chartPane = document.createElement("div");
          chartPane.className = "osm-split-chart";
          root.append(mapPane, bar, chartPane);
          element.appendChild(root);

          const { source, seriesKey } = domainObject.osm;
          map = createMap(mapPane);

          get(source).then(({ series, places }) => {
            const s = series.series.find((x) => x.key === seriesKey);
            if (!s || !root) return;

            let selected = null;
            const show = () => {
              const shown = placesAt(places, selected);
              map.setFeatures(shown, { fit: selected !== null });
              bar.replaceChildren(
                label(selected === null ? "All days" : selected),
                count(shown),
                selected === null ? blank() : clear(() => pick(null)),
              );
            };
            const pick = (t) => {
              selected = selected === t ? null : t;
              draw();
              show();
            };
            const draw = () => {
              const box = chartPane.getBoundingClientRect();
              const w = Math.max(720, Math.round(box.width || 720));
              // The pane is sized in vh by the stylesheet; take what it got,
              // less the padding, and leave a floor so a short window still
              // produces a readable chart rather than a smear.
              const h = Math.max(170, Math.round(box.height || 0) - 14);
              chartPane.replaceChildren(renderChart(s, w, { selected, onPick: pick, height: h }));
            };

            draw();
            show();
            if (typeof ResizeObserver !== "undefined") {
              observer = new ResizeObserver(() => {
                draw();
                map.resize();
              });
              observer.observe(chartPane);
            }
          });
        },
        destroy() {
          if (observer) observer.disconnect();
          if (map) map.destroy();
          observer = null;
          map = null;
          root = null;
        },
      };
    },
  };
}

function label(text) {
  const e = document.createElement("span");
  e.className = "osm-split-day";
  e.textContent = text;
  return e;
}

function count(features) {
  const grounded = features.filter((f) => f.geometry).length;
  const e = document.createElement("span");
  e.className = "osm-split-count";
  e.textContent =
    features.length === grounded
      ? `${grounded} places`
      : `${grounded} places, ${features.length - grounded} without coordinates`;
  return e;
}

function clear(onClick) {
  const e = document.createElement("button");
  e.className = "osm-split-clear";
  e.type = "button";
  e.textContent = "show all days";
  e.addEventListener("click", onClick);
  return e;
}

function blank() {
  return document.createElement("span");
}
