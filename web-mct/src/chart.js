import { COLOUR } from "./palette.js";

const DEFAULT_H = 260;
const PAD = { top: 18, right: 18, bottom: 26, left: 48 };

/** Counts over time, with the baseline behind them.
 *
 * Hand-drawn SVG, not Open MCT's Plot. That is the documented safe path for
 * objects that come from a provider rather than from +Create: cafebabe's
 * patterns/open-mct-telemetry.md records three projects where Plot's metadata,
 * request() and legend all worked while the line itself never drew.
 *
 * A candidate is a band across the full height, not a dot on the line. A dot
 * is a few pixels you have to go looking for; a band is the first thing you
 * see, which is the right emphasis for the one thing the chart points at.
 *
 * `onPick` is optional: the chart on its own has nothing to drive, and only
 * becomes clickable when something is listening. `height` is optional too, and
 * the caller passes the pane's own height so the chart fills what the layout
 * gave it instead of a number chosen here.
 */
export function renderChart(s, w, opts = {}) {
  const { selected = null, onPick = null, height = DEFAULT_H } = opts;
  // Height comes from the pane rather than from a constant, so the chart uses
  // whatever the layout gives it. The caller decides how much that is.
  const H = height;
  const { t, value, baseline, anomalies, change_points, segments } = s;
  const n = t.length;
  const svg = el("svg", { viewBox: `0 0 ${w} ${H}`, width: w, height: H,
                          role: "img", "aria-label": `counts for ${s.key}` });
  if (n === 0) return svg;

  const iw = w - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const max = Math.max(1, ...value, ...baseline);
  const x = (i) => PAD.left + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v) => PAD.top + ih - (v / max) * ih;
  const half = n > 1 ? iw / (n - 1) / 2 : iw / 2;
  const path = (vs) =>
    vs.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  segments.forEach((sg, k) => {
    const x0 = x(sg.start) - half;
    const x1 = x(Math.max(sg.start, sg.end - 1)) + half;
    svg.appendChild(el("rect", { x: x0, y: PAD.top, width: Math.max(0, x1 - x0),
      height: ih, fill: k % 2 ? "rgba(56,189,248,.055)" : "rgba(148,163,184,.05)" }));
  });

  [0, 1, 2, 3, 4].map((k) => (max * k) / 4).forEach((v) => {
    svg.appendChild(el("line", { x1: PAD.left, y1: y(v), x2: w - PAD.right, y2: y(v),
      stroke: COLOUR.axis, "stroke-width": 1 }));
    svg.appendChild(text(PAD.left - 6, y(v) + 3, String(Math.round(v)),
      { fill: COLOUR.muted, "font-size": 10, "text-anchor": "end" }));
  });

  anomalies.forEach((a) => {
    svg.appendChild(el("rect", { x: x(a.i) - half, y: PAD.top, width: half * 2,
      height: ih, fill: selected === a.t ? "rgba(244,63,94,.45)" : "rgba(244,63,94,.22)" }));
  });

  segments.forEach((sg) => {
    const x0 = x(sg.start) - half;
    const x1 = x(Math.max(sg.start, sg.end - 1)) + half;
    svg.appendChild(el("line", { x1: x0, y1: y(sg.mean), x2: x1, y2: y(sg.mean),
      stroke: COLOUR.cp, "stroke-width": 2, "stroke-linecap": "round" }));
  });
  change_points.forEach((p) => {
    svg.appendChild(el("line", { x1: x(p.i) - half, y1: PAD.top,
      x2: x(p.i) - half, y2: PAD.top + ih, stroke: COLOUR.cp,
      "stroke-width": 1.4, "stroke-dasharray": "3 3" }));
    svg.appendChild(text(x(p.i) - half + 3, PAD.top + 11, p.t.slice(5, 10),
      { fill: COLOUR.cp, "font-size": 10 }));
  });

  svg.appendChild(el("path", { d: path(baseline), fill: "none",
    stroke: COLOUR.trend, "stroke-width": 1.6, "stroke-dasharray": "4 3" }));
  svg.appendChild(el("path", { d: path(value), fill: "none",
    stroke: COLOUR.series, "stroke-width": 2 }));

  value.forEach((v, i) => {
    const hit = anomalies.find((a) => a.i === i);
    svg.appendChild(el("circle", { cx: x(i), cy: y(v), r: hit ? 3.8 : 2.4,
      fill: hit ? COLOUR.hot : COLOUR.series }));
    const grab = el("rect", { x: x(i) - half, y: PAD.top, width: half * 2,
      height: ih, fill: "transparent" });
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${t[i]}  ${v}${hit ? `  z ${hit.score}` : ""}`;
    grab.appendChild(title);
    // Every bucket is clickable, not only the unusual ones. A quiet day next
    // to a loud one is worth looking at, and a hit area that appears only on
    // some columns is a worse target than one that is always there.
    if (onPick) {
      grab.style.cursor = "pointer";
      grab.addEventListener("click", () => onPick(t[i]));
    }
    svg.appendChild(grab);
  });

  const step = Math.max(1, Math.ceil(n / Math.max(4, Math.floor(iw / 130))));
  t.forEach((d, i) => {
    if (i % step) return;
    svg.appendChild(text(x(i), H - 8, d.slice(5, 10),
      { fill: COLOUR.muted, "font-size": 10, "text-anchor": "middle" }));
  });
  return svg;
}

function el(name, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

function text(x, y, content, attrs) {
  const node = el("text", { x, y, ...attrs });
  node.textContent = content;
  return node;
}
