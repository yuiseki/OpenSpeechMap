/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MAP_STYLE?: string;
  readonly VITE_SERIES_URL?: string;
  readonly VITE_PLACES_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
