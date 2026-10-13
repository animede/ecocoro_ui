# ecocoro 画像生成サーバー

`alfredplpl/ecocoro-preview-1` (FLUX.2-klein ベースのフルファインチューンモデル) を使った
画像生成サーバーです。テキストから生成 (T2I)、参照画像からの生成 (I2I)、指示ベースの画像編集 (Edit)
に対応し、生成結果はローカルに保存・一覧・ダウンロード・削除できます。
外部LLM (OpenAI互換API) を使ったプロンプト拡張・日英翻訳機能も付いています。

## ライセンス・利用上の注意

本リポジトリのソースコードは [Apache License 2.0](LICENSE) で提供します(著作権者: © 2026 YUZUKI (animede)、[NOTICE](NOTICE) 参照)。

- `alfredplpl/ecocoro-preview-1` 本体、ベースモデル `black-forest-labs/FLUX.2-klein-base-4B` とも **Apache License 2.0** で提供されており、商用利用を含め法的な利用制限はありません。
- ただし両モデルカードには、以下のような生成内容に関する利用ガイドラインが明記されています(ライセンス条項自体を制限するものではありませんが、遵守が求められます)。
  - 適用法に違反する用途、児童搾取・CSAMの生成/取得/拡散
  - 欺瞞的・詐欺的・誤解を招く有害コンテンツの生成
  - 個人識別情報 (PII) を悪用目的で生成・拡散すること
  - 嫌がらせ・脅迫・ストーキング目的の利用
  - 非同意の性的画像 (NCII) や違法なポルノコンテンツの生成
  - 個人の法的権利に不利益な影響を与える完全自動意思決定・高リスク用途
- 生成物は誤った解剖・手・文字などの欠陥を含む場合があるため、公開・商用利用前にユーザー自身によるレビューが必要です。
- このサーバー自体のライセンスは特に設定していません (社内/個人利用ツールとして実装)。公開する場合は別途ライセンスファイルの追加を検討してください。

## 必要環境

- Python 3.10 以上 (動作確認は 3.12)
- CUDA対応GPU (VRAM推奨: 24GB以上。実機は RTX PRO 6000 Blackwell 96GB を想定)
- `requirements.txt` に記載のパッケージ (バージョンは動作確認済みのもの)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

OpenAI互換のchat completions APIを提供するLLMサーバー (vLLM, Ollama等) が別途必要です。
プロンプト拡張・翻訳機能はこのLLMサーバーに依存します (画像生成自体には不要です)。

## 起動方法

`--llm-endpoint` は必須オプションです。指定しないと起動時にargparseエラーになります。

```bash
python run_server.py --llm-endpoint http://39.110.248.77:64650/v1
```

主なオプション:

| オプション | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `--llm-endpoint` | 必須 | なし | LLMサーバーのベースURL (`/chat/completions` を付与して呼び出します) |
| `--llm-model` | 任意 | `default` | LLMのモデル名 |
| `--llm-api-key` | 任意 | `EMPTY` | LLMサーバーのAPIキー |
| `--host` | 任意 | `0.0.0.0` | バインドホスト |
| `--port` | 任意 | `8000` | ポート |
| `--model-id` | 任意 | `alfredplpl/ecocoro-preview-1` | 使用する拡散モデルのHugging Face ID |
| `--outputs-dir` | 任意 | `./outputs` | 生成画像・メタデータDBの保存先 |
| `--device` | 任意 | `cuda` | 拡散モデルの実行デバイス |

起動後、ブラウザで `http://localhost:8000/` を開くとUIが表示されます。

拡散モデル本体は初回リクエスト時に遅延ロードされます (起動そのものはモデルロード無しで完了します)。

## APIエンドポイント一覧

### 画像生成

- `POST /api/t2i` — テキストから画像生成。JSON body: `prompt`, `negative_prompt?`, `width`, `height`, `steps`, `guidance_scale`, `seed?`, `num_images`
- `POST /api/i2i` — 参照画像からのバリエーション生成。multipart/form-data: `image` (ファイル), `prompt`, `negative_prompt?`, `width?`, `height?`, `steps`, `guidance_scale`, `seed?`, `num_images`
- `POST /api/edit` — 指示ベースの画像編集。multipart/form-data: `image` (ファイル), `instruction`, `negative_prompt?`, `width?`, `height?`, `steps`, `guidance_scale`, `seed?`, `num_images`

すべて生成画像はPNGとして `outputs/` に保存され、メタデータは `outputs/metadata.db` (SQLite) に記録されます。
レスポンスは生成画像のid一覧とメタデータのJSONです。

### 画像管理

- `GET /api/images` — 全画像のメタデータ一覧 (新しい順)
- `GET /api/images/{id}` — 画像そのもの (image/png、プレビュー用)
- `GET /api/images/{id}/download` — ダウンロード (Content-Dispositionでファイル名指定)
- `DELETE /api/images/{id}` — 画像削除 (ファイル・DBレコード両方)

### プロンプト支援 (LLM連携)

- `POST /api/prompt/expand` — body: `{text, mode: "t2i" | "i2i_edit"}`。簡単な指示から詳細なプロンプト/編集指示をLLMで生成
- `POST /api/prompt/translate` — body: `{text, direction: "ja2en" | "en2ja"}`。LLMによる翻訳

## 実装メモ・既知の制約

- GPUは1枚を想定し、生成呼び出しは `asyncio.Lock` で直列化しています。実際のパイプライン呼び出しは
  `run_in_executor` でワーカースレッドに逃がしており、イベントループはブロックされません。
- 使用パイプラインクラスは `diffusers.Flux2KleinPipeline` です (diffusers 0.39.0で動作確認)。
  実際の `__call__` シグネチャを確認したところ、`negative_prompt_embeds` 引数は
  **テキストではなく事前計算済みの `torch.Tensor` のみを受け付ける** 実装になっており
  (`encode_prompt(prompt_embeds=negative_prompt_embeds)` として内部で使われるため)、
  素のネガティブプロンプト文字列を直接渡す口はこのバージョンには存在しませんでした。
  そのためAPI/DB上は `negative_prompt` を受け付けて記録しますが、パイプライン呼び出しには渡していません
  (渡すと型不一致でクラッシュするため)。CFG (`guidance_scale > 1`) 自体は有効で、内部的には
  空文字列 `""` がネガティブプロンプトとして使われます。
- `image` に画像を渡すI2I/Edit呼び出し時は、`width`/`height` を明示的に渡さず参照画像側のサイズに
  委ねる実装にしています (パイプラインが自動でリサイズ・クロップ処理を行うため)。
- 生成時にアップロードされた元画像 (参照/編集対象) も内部的には `outputs/` に保存され、
  DB上は `type="source"` として記録されます。ギャラリー一覧 (`GET /api/images`) には含まれず、
  `i2i`/`edit` の生成結果の `source_image_id` から参照される内部レコードです。

## 動作確認状況

- `python -c "from backend.main import app"` によるインポート確認: 成功
- `run_server.py --help` で `--llm-endpoint` が必須項目として表示されること、および未指定時に
  argparseエラーで起動が拒否されることを確認済み
- ダミーの `--llm-endpoint` を指定してuvicornを実際に起動し、`GET /` がHTML、`GET /api/images` が
  空配列 `[]` を返すこと、静的ファイル (`/static/style.css`, `/static/app.js`) が配信されることを確認済み
- 実際のT2I生成もHugging Faceから本体モデルをダウンロードして試行しました。パイプラインのロード・
  推論呼び出し自体は正常に動作しましたが、検証時はGPU上に他プロセスが既に86GB前後を使用しており
  空きVRAMが約10GBしかなかったため、推論中にCUDA OOMが発生しました。
  エラーハンドリング (500エラーを分かりやすいメッセージで返す、サーバーが落ちない、DBに不整合な
  レコードが残らない) は正しく機能することを確認しています。
  十分な空きVRAM (数十GB) がある環境では最後まで生成が完了するはずですが、実画像の生成完了までは
  未検証です。
- LLM連携 (`/api/prompt/expand`, `/api/prompt/translate`) は実際のLLMサーバーに接続しての動作確認は
  行っていません (エラーハンドリングパス、httpxリクエストの構築は実装済み)。
