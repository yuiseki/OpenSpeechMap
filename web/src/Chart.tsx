import type { Series } from "./types";

interface Props {
  series: Series;
  selected: string | null;
  onPick: (t: string) => void;
}

const H = 170;
const PAD = { top: 14, right: 14, bottom: 22, left: 44 };

/** Colours live in one place, in index.css, so the chart and the map agree
 * about what a candidate looks like. SVG cannot take CSS variables in every
 * attribute, so they are read once. */
function palette() {
  const css = getComputedStyle(document.documentElement);
  const pick = (name: string, fallback: string) =>
    css.getPropertyValue(name).trim() || fallback;
  return {
    axis: pick("--line", "#1e293b"),
    muted: pick("--muted", "#94a3b8"),
    series: pick("--accent", "#38bdf8"),
    trend: pick("--trend", "#64748b"),
    hot: pick("--hot", "#f43f5e"),
    cp: pick("--cp", "#a78bfa"),
    bg: pick("--bg", "#0f172a"),
  };
}

/** Counts over time, with the baseline behind them.
 *
 * A candidate is drawn as a band across the full height of the chart, not as a
 * dot on the line. A dot is a few pixels of a colour you have to go looking
 * for; a band is the first thing you see, which is the right emphasis for the
 * one thing the chart exists to point at.
 *
 * Change points get their own colour and their own shape: a dashed rule where
 * the level moved, and a horizontal line at the mean either side of it. A spike
 * and a shift in level are different answers and should not look alike.
 *
 * Hand-drawn SVG rather than a charting library: there is one chart, it needs
 * no configuration surface, and the click target has to line up with a date.
 */
export function Chart({ series, selected, onPick }: Props) {
  const { t, value, baseline, anomalies, change_points, segments } = series;
  const n = t.length;
  if (n === 0) return null;

  const colour = palette();
  const w = 900;
  const iw = w - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const max = Math.max(1, ...value, ...baseline);
  const x = (i: number) => PAD.left + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v: number) => PAD.top + ih - (v / max) * ih;
  const half = n > 1 ? iw / (n - 1) / 2 : iw / 2;
  const path = (vs: number[]) =>
    vs.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  const gridlines = [0, 1, 2, 3, 4].map((k) => (max * k) / 4);
  const step = Math.max(1, Math.floor(n / 9));
  const ticks = t.map((d, i) => ({ d, i })).filter(({ i }) => i % step === 0);

  return (
    <svg viewBox={`0 0 ${w} ${H}`} width="100%" height={H} role="img"
         aria-label={`counts for ${series.key}`}>
      {/* Alternating ground for the stretches between change points, so the
          boundaries read even where the mean barely moves. */}
      {segments.map((sg, k) => {
        const x0 = x(sg.start) - half;
        const x1 = x(Math.max(sg.start, sg.end - 1)) + half;
        return (
          <rect key={`seg-${sg.start}`} x={x0} y={PAD.top}
                width={Math.max(0, x1 - x0)} height={ih}
                fill={k % 2 ? "rgba(56,189,248,.055)" : "rgba(148,163,184,.05)"} />
        );
      })}

      {gridlines.map((v) => (
        <g key={`grid-${v}`}>
          <line x1={PAD.left} y1={y(v)} x2={w - PAD.right} y2={y(v)}
                stroke={colour.axis} strokeWidth={1} />
          <text x={PAD.left - 6} y={y(v) + 3} fill={colour.muted} fontSize="9"
                textAnchor="end">{Math.round(v)}</text>
        </g>
      ))}

      {/* The candidates, as bands. Selected one is stronger. */}
      {anomalies.map((a) => (
        <rect key={`band-${a.i}`} x={x(a.i) - half} y={PAD.top}
              width={half * 2} height={ih}
              fill={selected === a.t ? "rgba(244,63,94,.42)" : "rgba(244,63,94,.20)"} />
      ))}

      {/* Where the level moved, and what it moved between. */}
      {segments.map((sg) => {
        const x0 = x(sg.start) - half;
        const x1 = x(Math.max(sg.start, sg.end - 1)) + half;
        return (
          <line key={`mean-${sg.start}`} x1={x0} y1={y(sg.mean)} x2={x1} y2={y(sg.mean)}
                stroke={colour.cp} strokeWidth={2} strokeLinecap="round" />
        );
      })}
      {change_points.map((point) => (
        <g key={`cp-${point.i}`}>
          <line x1={x(point.i) - half} y1={PAD.top}
                x2={x(point.i) - half} y2={PAD.top + ih}
                stroke={colour.cp} strokeWidth={1.4} strokeDasharray="3 3" />
          <text x={x(point.i) - half + 3} y={PAD.top + 10} fill={colour.cp}
                fontSize="9">{point.t.slice(5, 10)}</text>
        </g>
      ))}

      <path d={path(baseline)} fill="none" stroke={colour.trend} strokeWidth={1.6}
            strokeDasharray="4 3" />
      <path d={path(value)} fill="none" stroke={colour.series} strokeWidth={2} />

      {value.map((v, i) => {
        const hit = anomalies.find((a) => a.i === i);
        return (
          <g key={`pt-${i}`}>
            <circle cx={x(i)} cy={y(v)} r={hit ? 3.6 : 2.2}
                    fill={hit ? colour.hot : colour.series} />
            {/* A full-height hit area per bucket, so a date can be picked
                without aiming at a two-pixel dot. */}
            <rect x={x(i) - half} y={PAD.top} width={half * 2} height={ih}
                  fill="transparent" style={{ cursor: hit ? "pointer" : "default" }}
                  onClick={hit ? () => onPick(hit.t) : undefined}>
              <title>{`${t[i]}  ${v}${hit ? `  z ${hit.score}` : ""}`}</title>
            </rect>
          </g>
        );
      })}

      {ticks.map(({ d, i }) => (
        <text key={`tk-${i}`} x={x(i)} y={H - 6} fill={colour.muted} fontSize="9"
              textAnchor="middle">{d.slice(5, 10)}</text>
      ))}
    </svg>
  );
}
