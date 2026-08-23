"""`speechmap.yaml`: declaring a pipeline instead of typing it.

The stage commands stay exactly as they are; this is a layer above them. The
point is not to hide the composition but to write it down, so that starting a
continuous run is one thing rather than three, and so that what somebody is
running can be read rather than reconstructed from shell history.

Everything is validated before any stage starts. A declaration that names a
lens which does not exist should fail in a second, not twenty minutes into a
transcription run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openspeechmap import lens as lens_module

SOURCE_KINDS = ("sdr", "http", "dir", "transcripts")


class ConfigError(Exception):
    """A declaration that cannot be used, with a message saying which part."""


@dataclass(frozen=True)
class Source:
    kind: str
    label: str = "REC"
    url: str = ""
    path: Path | None = None
    freq: str = ""
    gain: str = "19.7"
    device: str = "0"
    segment_sec: int = 300
    retention_hours: float = 168
    max_gb: float = 50


@dataclass(frozen=True)
class Transcribe:
    chunk_sec: int = 60
    whisper_url: str = "http://127.0.0.1:30180/inference"
    language: str = ""
    skip_newest: bool = True


@dataclass(frozen=True)
class LensStage:
    select: str = ".is_disaster"
    text_field: str = "text"
    id_field: str = "seg"
    place_field: str = "topic"
    time_field: str = "t"
    model: str = "gvt-llm"
    llm_url: str = "http://127.0.0.1:8080/v1"
    loci_url: str = "http://127.0.0.1:30101"
    concurrency: int = 6


@dataclass(frozen=True)
class Series:
    bucket: str = "day"
    key_field: str = "category"
    select: str = ".is_disaster"
    threshold: float | None = None


@dataclass(frozen=True)
class Config:
    path: Path
    out: Path
    source: Source
    lens: lens_module.Lens
    transcribe: Transcribe = field(default_factory=Transcribe)
    lens_stage: LensStage = field(default_factory=LensStage)
    series: Series = field(default_factory=Series)

    def stages(self) -> list[str]:
        """Which stages this declaration implies.

        A declaration says where the speech comes from, and that decides how
        much of the chain has to run. Someone who already has transcripts should
        not have to say "and do not record anything".
        """
        if self.source.kind == "transcripts":
            return ["lens", "series"]
        if self.source.kind == "dir":
            return ["transcribe", "lens", "series"]
        return ["record", "transcribe", "lens", "series"]

    @property
    def recordings(self) -> Path:
        return self.source.path or (self.out / "recordings")

    @property
    def transcripts(self) -> Path:
        if self.source.kind == "transcripts":
            return self.source.path  # type: ignore[return-value]
        return self.out / "transcripts"


def load(path: str | Path) -> Config:
    """Read and validate a declaration."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise ConfigError(f"no such file: {path}")
    try:
        import yaml
    except ModuleNotFoundError as e:  # pragma: no cover
        raise ConfigError(
            "reading speechmap.yaml needs PyYAML: pip install 'openspeechmap[config]'"
        ) from e
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{p.name}: not valid YAML ({e})") from e
    if raw is None:
        raise ConfigError(f"{p.name} is empty")
    if not isinstance(raw, dict):
        raise ConfigError(f"{p.name}: the top level must be a mapping of settings")

    base = p.parent.resolve()
    known = {"source", "out", "lens", "transcribe", "lens_stage", "series"}
    _reject_unknown(raw, known, where=p.name)

    for required in ("out", "lens", "source"):
        if required not in raw:
            raise ConfigError(f"{p.name}: {required} is required")

    source = _source(raw["source"], base=base, where=p.name)
    lens_path = _resolve(base, raw["lens"])
    try:
        lens = lens_module.load(lens_path)
    except lens_module.LensError as e:
        raise ConfigError(f"{p.name}: lens: {e}") from e

    return Config(
        path=p,
        out=_resolve(base, raw["out"]),
        source=source,
        lens=lens,
        transcribe=_section(Transcribe, raw.get("transcribe"), "transcribe", p.name),
        lens_stage=_section(LensStage, raw.get("lens_stage"), "lens_stage", p.name),
        series=_section(Series, raw.get("series"), "series", p.name),
    )


def _resolve(base: Path, value: Any) -> Path:
    """Paths are relative to the declaration, not to the working directory.

    A file you can hand to someone else has to mean the same thing wherever it
    is run from, including from a timer with no meaningful cwd.
    """
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _reject_unknown(given: dict, known: set[str], *, where: str) -> None:
    """Refuse a key nobody reads.

    Ignoring it means the setting the person believes they have set is not set,
    and the run does something other than what the file says.
    """
    unknown = sorted(set(given) - known)
    if unknown:
        raise ConfigError(
            f"{where}: unknown setting(s): {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(known))}"
        )


def _section(cls, given: Any, name: str, where: str):
    if given is None:
        return cls()
    if not isinstance(given, dict):
        raise ConfigError(f"{where}: {name} must be a mapping")
    known = {f.name for f in cls.__dataclass_fields__.values()}
    _reject_unknown(given, known, where=f"{where}: {name}")
    return cls(**given)


def _source(given: Any, *, base: Path, where: str) -> Source:
    if not isinstance(given, dict):
        raise ConfigError(f"{where}: source must be a mapping")
    known = {f.name for f in Source.__dataclass_fields__.values()}
    _reject_unknown(given, known, where=f"{where}: source")

    kind = str(given.get("kind", ""))
    if kind not in SOURCE_KINDS:
        raise ConfigError(
            f"{where}: source.kind must be one of {', '.join(SOURCE_KINDS)}, "
            f"not {kind!r}"
        )
    values = dict(given)
    if "path" in values:
        values["path"] = _resolve(base, values["path"])

    if kind == "http" and not values.get("url"):
        raise ConfigError(f"{where}: source.kind is http, so source.url is required")
    if kind == "sdr" and not values.get("freq"):
        raise ConfigError(f"{where}: source.kind is sdr, so source.freq is required")
    if kind in ("dir", "transcripts"):
        path = values.get("path")
        if not path:
            raise ConfigError(f"{where}: source.kind is {kind}, so source.path is required")
        if not Path(path).exists():
            raise ConfigError(f"{where}: source.path does not exist: {path}")

    return Source(**values)
