# Architecture Decision Records

OpenSpeechMap の主要な設計判断の記録。なぜそうしたかと、何を却下したか。

| # | 決定 | 状態 |
|---|---|---|
| [0001](0001-agent-driven-not-gui.md) | エージェントが駆動する前提で設計し、GUI を作らない | Accepted (2026-08-23) |
| [0002](0002-lenses-as-data.md) | レンズをコードではなくデータにする | Accepted (2026-08-23) |
| [0003](0003-bind-existing-oss.md) | 既存 OSS を束ね、隙間だけを作る | Accepted (2026-08-23) |
| [0004](0004-input-is-timestamped-text.md) | 入力面は時刻付きテキストであり、音声ではない | Accepted (2026-08-23) |
| [0005](0005-place-identity-by-osm-id.md) | 地点の同一性を osm_id で判定し、正規化辞書を持たない | Accepted (2026-08-23) |
| [0006](0006-candidates-not-verdicts.md) | 判定ではなく候補を返し、閾値は道具の外に置く | Accepted (2026-08-23) |
| [0007](0007-provenance-on-every-record.md) | 各レコードに provenance を持たせる | Accepted (2026-08-23) |
| [0008](0008-geographic-scoping.md) | 集計を地理的スコープに閉じる | Accepted (2026-08-23) |
| [0009](0009-accepting-the-osm-acronym.md) | 略称が OSM になることを受け入れる | Accepted (2026-08-23) |
| [0010](0010-series-is-a-separate-command.md) | 時系列は別コマンドにし、地点に時刻を持たせる | Accepted (2026-08-23) |
| [0011](0011-viewer-is-vite-react-typescript.md) | ビューアは Vite + React + TypeScript にする | Accepted (2026-08-23) |
| [0012](0012-python-for-the-cli.md) | CLI は Python で書き、外部プログラムの薄いラッパーに留める | Accepted (2026-08-23) |
| [0013](0013-capture-belongs-here.md) | 常時録音をこのリポジトリに置く | Accepted (2026-08-23) |
| [0014](0014-transcription-belongs-here.md) | 文字起こしを置き、時刻の決め方を明文化する | Accepted (2026-08-23) |
| [0015](0015-idempotent-stages-and-a-declaration.md) | 段を冪等にし、合成を speechmap.yaml で宣言する | Accepted (2026-08-23) |

## 前史

このリポジトリは PoC から切り出された。切り出し前の意思決定、特に録音・ASR・GPU 配分・
多言語対応に関するものは PoC 側の ADR にある。ここには、束ねる側の設計として引き継いだ
判断だけを置く。
