#!/usr/bin/env bash
# Generate the synthetic transcripts the tests run against.
#
# Run once; commit the result. The tests themselves never call a language
# model: the same prompt does not produce the same output twice, so a test that
# generated its own input would be measuring the weather.
#
# These are synthetic on purpose. Tests need transcripts that read like
# broadcast speech, including the misrecognitions a speech recogniser makes,
# and shipping recordings of an actual broadcaster in a public repository is a
# licensing question this project does not need to have.
#
# usage: tests/fixtures/generate.sh [LLM_URL] [MODEL]
set -euo pipefail

LLM_URL="${1:-${LLM_URL:-http://127.0.0.1:8080/v1}}"
MODEL="${2:-${MODEL:-gvt-llm}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/transcripts.jsonl"

# Each line: an id, a time, and what the transcript must contain. The cases are
# chosen to exercise the decisions the pipeline makes, not to be representative
# of broadcast in general.
#
# The specs and the prompt below are in Japanese because what they ask for is
# Japanese broadcast speech, down to the misrecognitions a recogniser makes on
# Japanese place names. Asking in English produces worse Japanese.
read -r -d '' CASES <<'EOF' || true
d1|2026-08-13T19:00:00|千葉県柏市と市原市で記録的短時間大雨が降り、気象庁が警報を出したという気象情報。市区町村名をはっきり言う。
d2|2026-08-13T19:05:00|茨城県守谷市に土砂災害警戒情報レベル4が出て避難を呼びかける放送。ただし「守谷市」を音声認識が「森谷市」と誤認識した形で書く。
d3|2026-08-13T20:00:00|千葉県内の河川が氾濫危険水位に近づいているという情報。河川名を2つ挙げる。「氾濫」を音声認識が「反乱」と誤認識した形で書く。
d4|2026-07-28T16:30:00|熊本県益城町で震度6強の地震が発生した速報。余震への注意を呼びかける。
d5|2026-08-01T07:00:00|関東地方の広い範囲を指すだけで市区町村名を一切含まない、ぼんやりした大雨の見通し。
n1|2026-08-13T19:10:00|高校野球の試合結果を伝える放送。地名は学校名の一部としてだけ出る。
n2|2026-08-14T10:00:00|語学講座で英語の発音を解説している放送。地名は出さない。
n3|2026-08-14T11:00:00|リスナーからの手紙を読み上げて雑談する放送。地名は出さない。
e1|2026-08-02T18:00:00|新潟県長岡市の花火大会の交通規制と会場案内を伝える放送。開催日と会場を言う。
e2|2026-08-02T18:30:00|「花火」という言葉が歌詞に出てくる楽曲を紹介するだけの音楽番組。実際の催事の開催は一切報じない。
e3|2026-08-03T12:00:00|江戸時代の花火の歴史を解説する教養番組。現在開催される催事の情報は含まない。
m1|2026-08-14T12:00:00|曲が終わって次の曲を紹介するだけのMC。地名も催事も災害も含まない。
EOF

: > "$OUT"
n=0
while IFS='|' read -r id t spec; do
  [ -n "${id:-}" ] || continue
  prompt=$(cat <<PROMPT
日本のラジオ放送を文字起こししたものを1つ作ってください。次の条件に従います。

- 約1分ぶん、200字から400字程度の日本語
- アナウンサーが実際に喋った通りの、読点で繋がる話し言葉
- 見出しや箇条書きにしない。説明や注釈を付けない
- 音声認識の出力なので句読点は不完全でよい
- 内容: ${spec}

文字起こしの本文だけを出力してください。
PROMPT
)
  body=$(jq -n --arg m "$MODEL" --arg p "$prompt" \
    '{model: $m, messages: [{role: "user", content: $p}], temperature: 0.8, max_tokens: 700}')
  text=$(curl -s "$LLM_URL/chat/completions" \
    -H 'Content-Type: application/json' -d "$body" \
    | jq -r '.choices[0].message.content // empty' \
    | tr -d '\r' | tr '\n' ' ' | sed 's/  */ /g; s/^ //; s/ $//')
  if [ -z "$text" ]; then
    echo "generate: no text came back for $id" >&2
    exit 1
  fi
  jq -c -n --arg seg "$id" --arg t "$t" --arg text "$text" \
    '{t: $t, seg: $seg, text: $text}' >> "$OUT"
  n=$((n + 1))
  echo "generate: $id" >&2
done <<< "$CASES"

# One record with empty text, written by hand rather than generated: the point
# is that the pipeline emits a row for it instead of dropping it.
jq -c -n '{t: "2026-08-14T13:00:00", seg: "z1", text: ""}' >> "$OUT"

echo "generate: wrote $((n + 1)) transcripts to $OUT" >&2
