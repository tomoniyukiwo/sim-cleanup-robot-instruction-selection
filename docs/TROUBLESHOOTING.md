# uv版の導入・切り分け

## 環境を混ぜない
既存`.venv`は保存し、新しい`.venv-uv`を使用。端末ごとにプロジェクト直下で`source scripts/uv_env.sh`を実行する。個別のpip installは行わず、pyprojectとuv.lockを一緒に使う。

```bash
source scripts/uv_env.sh
uv sync --locked --python 3.12
uv pip check --python "$UV_PROJECT_ENVIRONMENT/bin/python"
uv run --locked cleanup-robot doctor
```

## lockが古い／一致しない
更新版のpyproject.tomlとuv.lockを両方反映する。通常はuv sync --locked。意図して依存を変更した場合だけuv lockで更新。CUDAの配布元指定もpyprojectに含める。

## pandas / NumPy
NumPy2.2.6・pandas2.2.3・SciPy1.14.1へまとめて固定済み。旧手順のNumPy1.26.4固定は使用しない。読み込み失敗時はuv runで実行しているか、作業フォルダ内にpandas.py/numpy.py等がないか確認し、Traceback全体を記録する。pip checkが成功しても、実際のimportsとGPU実行は別途確認が必要。

## egl_probe
uv設定で分離ビルドへcmake3.31.6・setuptools・wheelを追加。C/C++とEGL開発ヘッダはOS側に必要。READMEのapt依存を準備し、CMakeの最初のエラーから確認する。uvはPython依存を解決するが、システムライブラリやドライバの不足は解決しない。

## cleanup-robotが見つからない
`uv run --locked cleanup-robot doctor`を使う。uv syncが失敗した場合はそのエラーが先。シェルのPATHに常駐させる必要はない。

## CUDA / EGL
nvidia-smiでGPUとドライバを確認。Torchはcu128へ固定。MUJOCO_GL=eglをPython起動前に設定。libegl1とNVIDIAドライバが必要。doctorはCUDA・importsの確認で、EGL描画までを検証するコマンドではない。

## モデル取得
prepareで公開のSmolVLA-LIBERO、SmolVLM2設定・processor、埋め込みモデルを取得。同一キャッシュの既存ファイルは再利用。smolvla_baseの6次元モデルをLIBEROの8/7次元へ無理に接続しない。学習データセットは推論のみなら不要だが、環境のアセット・初期状態は必要。

## 段階的に確認
doctor→prepare→catalog→公式smoke→独自route→独自runの順。同じ環境変数を使う。配布版を更新した場合もmodels/assets.lock.jsonや既存の実行結果を不用意に上書きしない。

## 指示と再試行
まず標準指示で１タスクを実行。曖昧なら保留。task-idを指定した実行は自動言語解釈の実績としない。再試行は原因診断やオンライン学習ではなく、現在状態からの再推論であり改善は保証しない。

## 動画
動画は推論待ちを除いたシミュレーション時間表示で、処理の実時間ではない。result.jsonのwall_secondsも確認。提出用には1〜3分に編集し、倍速や推論待ち省略を明記する。

## LeRobotのaggregate_statsをimportできない
こちらの導入検証では、キャッシュされたLeRobotのcompute_stats.pyが0バイトのケースがあり、上流の同一commitは正常だった。該当エラーが実際に出た場合に限り、uvのLeRobotパッケージキャッシュだけを再取得する。
```bash
source scripts/uv_env.sh
uv cache clean lerobot
uv sync --locked --reinstall-package lerobot --refresh-package lerobot
```
Hugging Faceのモデルキャッシュを削除する操作ではない。

## 初回LIBEROパスの入力待ち
setupでプロジェクト内のLIBEROパス設定を作るため、初回の対話入力を避ける。新しい端末でuv_env.shをsourceする。手動で直す場合は`uv run --locked python scripts/init_libero.py`。既存のプロジェクト設定は自動上書きしない。

## 公式eval動画が速すぎる
同梱official_eval_video.pyがLiberoEnvの保存用render_fpsを80から20へ設定してから公式evalを呼ぶ。env.fpsだけ変更しても公式evalはmetadataを参照するため今回の修正にはならない。既存動画はretime_video.pyで調整。動作や推論速度とは別の保存・再生速度の問題。
