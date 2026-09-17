import { get } from "../data.js";
import { renderChart } from "../chart.js";

/** The counts on their own, filling the pane.
 *
 * Kept next to the combined view because a chart with nothing under it can be
 * read at a glance, and a wall display showing one series wants the height.
 */
export function seriesView() {
  return {
    key: "osm.series.chart",
    name: "Counts",
    cssClass: "icon-telemetry",
    canView: (domainObject) => domainObject.type === "osm.series",
    view: (domainObject) => {
      let holder = null;
      let observer = null;
      return {
        show(element) {
          holder = document.createElement("div");
          holder.className = "osm-chart";
          element.appendChild(holder);
          const { source, seriesKey } = domainObject.osm;
          get(source).then(({ series }) => {
            const s = series.series.find((x) => x.key === seriesKey);
            if (!s || !holder) return;
            const draw = () => {
              const box = holder.getBoundingClientRect();
              const w = Math.max(720, Math.round(box.width || 720));
              const h = Math.max(170, Math.round(box.height || 0) - 24);
              holder.replaceChildren(renderChart(s, w, { height: h }));
            };
            draw();
            if (typeof ResizeObserver !== "undefined") {
              observer = new ResizeObserver(draw);
              observer.observe(holder);
            }
          });
        },
        destroy() {
          if (observer) observer.disconnect();
          observer = null;
          holder = null;
        },
      };
    },
  };
}
