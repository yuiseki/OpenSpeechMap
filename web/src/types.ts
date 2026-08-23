/** The two files the viewer reads. Both come out of the CLI unchanged. */

/** One series as detempus returns it. `method` is its own record of how the
 * answer was produced; it is displayed rather than interpreted. */
export interface Series {
  key: string;
  n: number;
  t: string[];
  value: number[];
  baseline: number[];
  residual: number[];
  score: number[];
  anomalies: Anomaly[];
  change_points: ChangePoint[];
  segments: Segment[];
  method: Record<string, string | number | boolean>;
}

export interface Anomaly {
  i: number;
  t: string;
  value: number;
  score: number;
}

export interface ChangePoint {
  i: number;
  t: string;
}

export interface Segment {
  start: number;
  end: number;
  mean: number;
}

/** `series.json`: detempus's answer, wrapped with how the run was set up. */
export interface SeriesFile {
  generated: string;
  bucket: "day" | "hour";
  select: string;
  key_field: string | null;
  series: Series[];
}

/** A feature of `places.geojson`. `t` is joined on by the CLI, so a place
 * knows when it was said and the viewer never has to look it up. */
export interface PlaceProperties {
  input_id: string;
  mention: string | null;
  status: "resolved" | "rejected" | "no_candidate" | "no_mention";
  osm_type?: string | null;
  osm_id?: number | null;
  display_name?: string | null;
  country_code?: string | null;
  t?: string | null;
}

export interface PlaceFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] } | null;
  properties: PlaceProperties;
}

export interface PlacesFile {
  type: "FeatureCollection";
  features: PlaceFeature[];
}
