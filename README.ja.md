# OpenSpeechMap

発話の中から、探している兆候を見つけて、地図と時系列に置く。

地方のラジオ局は、浸水した区の名前、決壊した河川、通行止めになった道路を、それが構造化されたデータになる何時間も前に言う。OpenSpeechMap はそれを聞き、自分で定義したレンズで何が重要かを判定し、地名を OpenStreetMap に接地して、GeoJSON を出す。

テーマは自分で決める。災害でも、人道安全保障でも、平和維持への脅威でも、祭りでもよい。レンズはテキスト 3 ファイルで、コードの変更ではない。

English: [README.md](README.md)

## 動かす

以下は、そのとおりに辿れば動く 1 本道である。公共ラジオのストリームを録音し、文字起こしし、災害報道を探し、見つけたものを地図に置く。

### 1. 入れる

```bash
git clone https://github.com/yuiseki/OpenSpeechMap && cd OpenSpeechMap
uv venv && source .venv/bin/activate && uv pip install -e .
```

以降のコマンドはすべてこの有効化されたシェルで実行する。端末を開き直したら先に `source .venv/bin/activate` をやり直すこと。でないと `speechmap` が見つからない。

次に、同梱していない駆動対象のプログラム。

```bash
sudo apt install ffmpeg jq curl               # macOS: brew install ffmpeg jq curl
uv pip install 'detempus[all] @ git+https://github.com/yuiseki/detempus'
git clone https://github.com/yuiseki/aiq        .tools/aiq
git clone https://github.com/yuiseki/locitorium .tools/locitorium
export AIQ="$PWD/.tools/aiq" LOCITORIUM="$PWD/.tools/locitorium"
```

この 3 つはどれもまだ PyPI に無い。`aiq` と `locitorium` を clone するのは、それぞれ自分の環境を必要とするからである。`speechmap` は `AIQ` と `LOCITORIUM` が指す checkout から実行する。

この 2 つは checkout 内の `.tools/` に落ちる。gitignore してあるので `git status` を汚さず、`rm -rf .tools` で元に戻せる。既に別の場所に持っているなら clone は飛ばして、2 つの変数をそこに向ければよい。有効化した venv と同じく、どちらの変数も `speechmap` を実行するシェルで設定されている必要がある。毎回打ちたくなければ永続する場所に置くこと。

加えて 3 つのサービスが動いている必要がある。OpenAI 互換の LLM エンドポイント、whisper.cpp サーバー、そして Nominatim を後ろに置いた locitorium。どれもクラウド API ではない。それぞれの起動方法、他のプラットフォームでのパッケージ名、`--source sdr` に追加で必要なものは [docs/PREREQUISITES.md](docs/PREREQUISITES.md) にある。

先に確認する。

```bash
speechmap check
```

### 2. 何を聞くか宣言する

```bash
cp speechmap.example.yaml speechmap.yaml
# 中の 3 つのエンドポイントと model を書き換えて、
speechmap --plan
```

同梱の example は、NPR の公開ストリームを録音して英語の災害報道を探す構成になっている。コメントが付いていて、電波から受ける場合や、既にある録音から始める場合の代替も書いてある。

`--plan` は何が走るかと、捕獲を起動する正確なコマンドを印字する。作業を一切せずに宣言を検証するので、パスの誤りは 20 分後ではなく 1 秒で分かる。

### 3. 起動する

```bash
speechmap
```

これで全部である。録音し、1 分ごとに、届いた分を文字起こしし、レンズを当て、時間で数える。Ctrl-C で止まる。

```
speechmap: capture and passes every 60s; Ctrl-C to stop
   transcribe  nothing recorded yet
   transcribe  4 file(s) -> 4 chunks -> 4 records (0 with no speech)
   lens        4 file(s) -> 4 records; 4 labelled, 3 selected, 8 places (7 resolved)
   series      3 counted -> 3 series, 0 candidates, 0 change points
```

各段は冪等なので、変化のない入力に対する 1 回の pass はディレクトリを一覧する費用しかかからない。`0 selected` は正常な答えである。放送の 1 日の大半は探しているものについて語っていない。捕獲と pass は独立しているので、モデルのエンドポイントが 1 分落ちても、1 週間録り続けている実行は終わらない。

### 4. 見つけたものを見る

```bash
cd web && npm install && npm run dev
```

地点を置いた地図、時間ごとの件数、そして普通でない区間が出る。同梱のサンプル出力から開くので、自分の実行がまだ何も出していない段階でも見るものがある。

## ストリームについて

NPR はこれを聴取のために公開しており、これはラジオがやるのと同じ読み方をしている。向ける先の規約は確認してほしい。公共放送を選ぶのが無難で、彼らは概して自分たちの放送が聴かれることを意図している。

言語に固有のものは何も無い。例で使っている英語レンズは `lenses/en-radio-disaster/` の 3 つのテキストファイルで、隣にある日本語のものも同じように書いた。コードは書いていない。

## 現状

| 段 | 状態 |
|---|---|
| 捕獲、文字起こし、レンズ、地名接地、時系列、ビューア | 動く |
| 事象ごとの地図生成 | 試作にある。地理的スコープ、対応フェーズでの色分け |

## どこに何があるか

| | |
|---|---|
| [docs/COMMANDS.md](docs/COMMANDS.md) | 各コマンド単体と、そのオプションが何のためにあるか |
| [docs/PREREQUISITES.md](docs/PREREQUISITES.md) | 何を入れるか。段ごと、プラットフォームごと |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 鎖の形、何を束ねているか、冪等性 |
| [docs/ADR/](docs/ADR/) | なぜこうなっているか、何を却下したか |
| [AGENTS.md](AGENTS.md) | これを駆動するエージェント向けの契約 |
| [lenses/README.md](lenses/README.md) | 自分のテーマのレンズを書く |
| [tests/README.md](tests/README.md) | テストがモデルを必要としない仕組み |

## ライセンス

MIT
