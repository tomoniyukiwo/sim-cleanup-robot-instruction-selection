# シミュレーション片付けロボットの指示選択比較

**Comparing Local LLM and Similarity-Based Instruction Selection for a Simulated Cleanup Robot**

自然言語の指示を登録済みのLIBEROタスクへ対応付け、SmolVLAでロボットアームを操作する実験用コードです。指示選択にはローカルのQwen3.5-2Bを使用し、多言語MiniLMによる類似度検索と比較します。ROS 2 Humbleは指示受付と実行監視を担当し、物理シミュレーションと目標判定にはLIBERO/MuJoCoを使用します。

Qwenには指示とタスク一覧のテキストを渡します。カメラ画像とロボット状態を使うのはSmolVLAです。選択後は登録タスクの英語標準指示をSmolVLAへ渡します。各タスクはシーンを初期化して個別に実行します。実機、外部推論API、独自の追加学習は使用していません。

## 実験の範囲と結果

[task 0の2例](tasks/fewshot_task0.json)をQwen3.5のfew-shot例とし、[task 1〜9の評価ケース](tasks/comparison_cases_qwen35.json)を事前に固定しました。指示選択の1回の測定では、Qwen3.5が24件中22件、MiniLMが24件中21件で期待した判断を返しました。遠回しな指示9件に限ると、それぞれ9件、8件です。情報不足の指示では、確認・保留と誤った実行判断を区別して集計しています。MiniLMの保留は自然言語の確認質問ではありません。

SmolVLAの操作は、task IDを明示して各タスク1回ずつ測定しました。task 1〜6、8、9はLIBEROの目標条件を達成し、task 7は200ステップで未達でした（8/9）。この9件は共通の操作試行であり、Qwen3.5とMiniLMがそれぞれ独立にロボットを動かした結果ではありません。Qwen3.5を組み込んだROS経路での物理操作、停止・再開、再試行の効果は未測定です。測定条件と結果の詳細は[検証状況](docs/VALIDATION.md)を参照してください。

## 動作環境

- Ubuntu 22.04.5 LTS、NVIDIA RTX 4060 Ti（VRAM 16GB）で確認
- Python 3.12、uv 0.13.4以上、CUDA対応PyTorch、ffmpeg
- ROS 2 Humble（ROSプロセスはシステムPythonで実行）
- SmolVLA用の依存はルートの`pyproject.toml`と`uv.lock`、Qwen3.5用は`planner_env/`内の別のlockで管理

GPU、EGL、LIBEROのシステム依存が必要です。セットアップ時の問題は[トラブルシューティング](docs/TROUBLESHOOTING.md)を参照してください。公開モデルの初回取得にはネット接続が必要です。モデル推論には外部APIを使用しません。

## セットアップ

以下はリポジトリのルートで実行します。モデル重み、モデル資産lock、仮想環境は配布コードに含まれないため、この環境で生成します。既存のモデル資産lockがある環境では`prepare`を再実行せず、そのlockを使ってください。

```bash
source scripts/uv_env.sh
uv sync --locked --python 3.12
uv run --locked python scripts/init_libero.py
uv run --locked cleanup-robot doctor
uv run --locked cleanup-robot prepare --out models/assets.lock.json
```

`prepare`はSmolVLA、MiniLM、LIBEROアセットを取得し、ローカルの保存先とrevisionを資産lockへ記録します。続けてQwen3.5専用環境を準備します。各段階が完了してから次を実行してください。

```bash
bash scripts/setup_qwen35.sh sync
bash scripts/setup_qwen35.sh check
bash scripts/setup_qwen35.sh prepare
```

`prepare`は`models/assets.qwen35.lock.json`を生成し、Qwen3.5のrevisionを追加します。既存の`models/assets.lock.json`は保持します。各段階のログは`outputs/setup/`へ保存されます。ローカルパスを含むため公開しないでください。

## 指示選択だけを比較する

```bash
bash scripts/setup_qwen35.sh compare
```

ロボットを動かさず、Qwen3.5とMiniLMの判断を比較します。結果は実行ごとに新しい`outputs/comparison/<実行ID>/`へ保存されます。`summary.json`で条件別正答、誤実行判断、確認質問・保留、推論時間を確認してください。`results.jsonl`には各ケースの判断が入ります。曖昧な指示からタスクを推測して実行した場合は正答としません。モデル読み込み時間と推論時間は別に記録します。

## ロボットを実行する

ROS経路の起動と指示送信は[ROS 2の手順](docs/ROS_A.md)を参照してください。単独のSmolVLA試行を記録する場合は、次のコマンドでtask 1〜9をそれぞれ1回実行します。各タスクをseed 42、初期状態0、最大200ステップで個別に初期化します。

```bash
python3 scripts/record_task_clips.py
```

`outputs/physical_clips/<実行ID>/`に各タスクの`result.json`、`demo.mp4`、manifestを保存します。このコマンドはtask IDを明示しており、指示選択器ごとの物理成功率は測定しません。成功はLIBEROの目標条件で判定します。

## 比較動画を作る

指示選択の実行IDと物理試行の実行IDを指定します。

```bash
python3 scripts/build_physical_comparison_video.py \
  --run outputs/comparison/<選択実行ID> \
  --clips outputs/physical_clips/<物理実行ID>
```

約2分の動画を新しい`outputs/video/<実行ID>/`へ保存します。遠回しな指示9件について、Qwen3.5とMiniLMの選択結果・推論時間を左右同じ時間軸に表示し、枠内に実測した操作映像を置きます。両手法が同じタスクを選んだ場合は同じSmolVLA映像を再掲します。保留した側には操作映像を表示しません。確認質問は動画に含めません。画面上の選択時間にモデル読み込みやロボット制御時間は含まれません。[動画構成](docs/VIDEO_SCRIPT.md)にも説明があります。

## コードと制約

- `src/cleanup_robot/`: タスク選択、入力検査、操作制御、LIBERO接続
- `planner_env/`: Qwen3.5専用の依存と推論プロセス
- `ros/`: ROS 2の指示受付・監視
- `scripts/`: セットアップ、比較、記録、動画・レポート作成
- `tasks/`、`configs/`: 登録タスク、評価ケース、設定
- `tests/`: ロジックと出力形式のテスト（物理成功率の代わりにはなりません）

Qwenは画像や物体位置を見ていません。未知の物体への汎化、連続した複数タスク、実機動作は評価していません。速度は1回の逐次測定であり、モデル間の一般的な速度差を示しません。[設計](docs/DESIGN.md)と[外部資源](docs/THIRD_PARTY.md)に実装上の前提を記載しています。

```bash
PYTHONPATH=src uv run --locked python -m unittest discover -s tests -v
```

このリポジトリの自作コードは[MIT License](LICENSE)で公開します。モデル、ライブラリ、シミュレータなどの外部資源には各配布元の条件が適用されます。
