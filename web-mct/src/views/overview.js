import { get } from "../data.js";

/** One run at a glance: what it was, and what came out.
 *
 * A single custom view that builds its own DOM, rather than a Display Layout
 * holding several widgets. cafebabe's patterns/open-mct-telemetry.md records
 * that both sas0 and m3xx-fleet reached for Display Layout, found it does not
 * agree with objects that come from a provider, and settled on exactly this:
 * one object, one view, build the panel by hand.
 */
export function overviewView() {
  return {
    key: "osm.overview",
    name: "Overview",
    cssClass: "icon-info",
    canView: (domainObject) => domainObject.type === "osm.source",
    view: (domainObject) => {
      let holder = null;
      return {
        show(element) {
          holder = document.createElement("div");
          holder.className = "osm-overview";
          element.appendChild(holder);
          const source = domainObject.osm.source;
          get(source).then(({ series, places }) => {
            if (!holder) return;
            const resolved = places.features.filter((f) => f.properties.status === "resolved");
            const anomalies = series.series.reduce((n, s) => n + s.anomalies.length, 0);
            const changes = series.series.reduce((n, s) => n + s.change_points.length, 0);
            holder.replaceChildren(
              row("Lens", source.lens),
              row("Span", source.note),
              row("Bucket", series.bucket),
              row("Selection", series.select),
              row("Series", String(series.series.length)),
              row("Candidates", `${anomalies} unusual buckets, ${changes} change points`),
              row("Places", `${places.features.length} mentions, ${resolved.length} grounded`),
              row("Generated", series.generated),
              note(
                "Every point here is a candidate: a hypothesis that something " +
                  "may have happened at this place, at this time. Not a finding.",
              ),
            );
          });
        },
        destroy() {
          holder = null;
        },
      };
    },
  };
}

function row(label, value) {
  const dl = document.createElement("div");
  dl.className = "osm-row";
  const k = document.createElement("span");
  k.className = "osm-row-key";
  k.textContent = label;
  const v = document.createElement("span");
  v.className = "osm-row-value";
  v.textContent = value;
  dl.append(k, v);
  return dl;
}

function note(text) {
  const p = document.createElement("p");
  p.className = "osm-note";
  p.textContent = text;
  return p;
}
