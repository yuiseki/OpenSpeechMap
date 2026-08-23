import { useMemo, useState } from "react";
import { Chart } from "./Chart";
import { MapView } from "./MapView";
import { bucketOf, useData } from "./useData";
import type { PlaceFeature } from "./types";

export function App() {
  const { data, error } = useData();
  const [key, setKey] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  const series = useMemo(() => {
    if (!data) return null;
    const list = data.series.series;
    if (list.length === 0) return null;
    const chosen = key ? list.find((s) => s.key === key) : null;
    if (chosen) return chosen;
    // Default to the series with the single most extreme candidate, not the
    // one with the most of them. Counting candidates promotes noisy
    // catch-all categories; the biggest deviation is what someone opening
    // this actually wants to see first.
    const peak = (s: (typeof list)[number]) =>
      s.anomalies.reduce((m, a) => Math.max(m, a.score), 0);
    return [...list].sort((a, b) => peak(b) - peak(a))[0] ?? null;
  }, [data, key]);

  const shown: PlaceFeature[] = useMemo(() => {
    if (!data) return [];
    const bucket = data.series.bucket;
    return data.places.features.filter((f) => {
      if (!f.geometry) return false;
      if (!picked) return true;
      return bucketOf(f.properties.t, bucket) === picked;
    });
  }, [data, picked]);

  if (error) {
    return (
      <div className="fatal">
        <h1>Could not load the output</h1>
        <p>{error}</p>
        <p>
          The viewer reads <code>series.json</code> and <code>places.geojson</code>.
          Point <code>VITE_SERIES_URL</code> and <code>VITE_PLACES_URL</code> at
          the directory <code>speechmap</code> wrote.
        </p>
      </div>
    );
  }
  if (!data || !series) return <div className="fatal">Loading…</div>;

  const withPlaces = new Set(
    data.places.features
      .filter((f) => f.geometry)
      .map((f) => bucketOf(f.properties.t, data.series.bucket)),
  );

  return (
    <>
      <div className="map">
        <MapView features={shown} />
      </div>

      <aside className="panel">
        <h1>OpenSpeechMap</h1>

        <label>
          series
          <select value={series.key} onChange={(e) => { setKey(e.target.value); setPicked(null); }}>
            {data.series.series.map((s) => (
              <option key={s.key} value={s.key}>
                {s.key} ({s.anomalies.length})
              </option>
            ))}
          </select>
        </label>

        <div className="boxes">
          <div className="box">
            <div className="num">{series.n}</div>
            <div className="lbl">buckets</div>
          </div>
          <div className="box">
            <div className="num">{series.value.reduce((a, b) => a + b, 0)}</div>
            <div className="lbl">counted</div>
          </div>
          <div className="box">
            <div className="num hot">{series.anomalies.length}</div>
            <div className="lbl">candidates</div>
          </div>
          <div className="box">
            <div className="num cp">{series.change_points.length}</div>
            <div className="lbl">change points</div>
          </div>
        </div>

        <h2>candidates</h2>
        {series.anomalies.length === 0 ? (
          <p className="muted">None above the threshold. That is a normal answer.</p>
        ) : (
          <ul className="cands">
            {series.anomalies.map((a) => (
              <li key={a.t}>
                <button
                  className={picked === a.t ? "on" : ""}
                  onClick={() => setPicked(picked === a.t ? null : a.t)}
                >
                  <span className="d">{a.t}</span>
                  <span className="v">{a.value}</span>
                  <span className="s">z {a.score}</span>
                  {!withPlaces.has(a.t) && <span className="warn">no places</span>}
                </button>
              </li>
            ))}
          </ul>
        )}

        {picked && (
          <p className="muted">
            Showing {shown.length} place{shown.length === 1 ? "" : "s"} from {picked}.{" "}
            <button className="link" onClick={() => setPicked(null)}>show all</button>
          </p>
        )}

        <h2>how this was produced</h2>
        <p className="muted small">
          These are candidates, not verdicts. A score is emitted for every point;
          the threshold below is where the list above was cut.
        </p>
        <dl className="stats small">
          {Object.entries(series.method).map(([k, v]) => (
            <span key={k}><dt>{k}</dt><dd>{String(v)}</dd></span>
          ))}
          <span><dt>select</dt><dd>{data.series.select}</dd></span>
          <span><dt>generated</dt><dd>{data.series.generated}</dd></span>
        </dl>
      </aside>

      <div className="chart">
        <div className="legend">
          <span className="ttl">{series.key}</span>
          <span><i className="sw series" />counted</span>
          <span><i className="sw trend" />baseline</span>
          <span><i className="sw hot" />candidate</span>
          <span><i className="sw cp" />change point, segment mean</span>
        </div>
        <Chart series={series} selected={picked} onPick={(t) => setPicked(picked === t ? null : t)} />
      </div>
    </>
  );
}
