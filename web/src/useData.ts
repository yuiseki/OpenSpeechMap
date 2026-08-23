import { useEffect, useState } from "react";
import type { PlacesFile, SeriesFile } from "./types";

const SERIES_URL = import.meta.env.VITE_SERIES_URL ?? "./sample/series.json";
const PLACES_URL = import.meta.env.VITE_PLACES_URL ?? "./sample/places.geojson";

export interface Data {
  series: SeriesFile;
  places: PlacesFile;
}

/** Fetch both inputs. Failing loudly matters more than a spinner here: if the
 * viewer is pointed at output that does not exist, saying so is the useful
 * behaviour. */
export function useData() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [s, p] = await Promise.all([fetch(SERIES_URL), fetch(PLACES_URL)]);
        if (!s.ok) throw new Error(`${SERIES_URL}: HTTP ${s.status}`);
        if (!p.ok) throw new Error(`${PLACES_URL}: HTTP ${p.status}`);
        const series = (await s.json()) as SeriesFile;
        const places = (await p.json()) as PlacesFile;
        if (alive) setData({ series, places });
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return { data, error };
}

/** Truncate a timestamp to the bucket the series was built with, so a point on
 * the chart and a set of places can be matched up. */
export function bucketOf(t: string | null | undefined, bucket: "day" | "hour") {
  if (!t) return null;
  return t.slice(0, bucket === "hour" ? 13 : 10);
}
