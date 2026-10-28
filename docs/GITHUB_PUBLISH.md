# GitHub公開用コード

提出するのはZIPファイルのURLではなく、**public GitHubリポジトリのURL**。ZIPは使用コード一式を安全に移すための配布元で、公開先そのものではない。URL・アカウント名・commit SHAは公開後に実値を記入する。

## ZIPに入る内容

`python3 scripts/build_public_release.py --require-planner-lock --out cleanup_robot_qwen35_public.zip`で新しいZIPを作る。同名のZIPがあれば番号を付けて保存し、上書きしない。ルートの`README.md`、`pyproject.toml`、`uv.lock`、`planner_env/pyproject.toml`、`planner_env/uv.lock`、`src/`、`ros/`、`scripts/`、`configs/`、`tasks/`、`tests/`、`docs/`、ライセンスを含める。実験の再現手順、Qwen3.5・MiniLMの比較、SmolVLA実行、動画合成のコードが入る。

モデル重み、モデル資産lock、仮想環境、ローカルキャッシュ、生ログ、操作動画、Word草稿、フォントは含めない。実行結果の公開用サマリーを加える場合は、入力文と個人情報を目視確認したJSONだけを`--evidence evidence/ファイル名.json`で指定する。

## 公開手順

1. ZIPを展開し、中の`cleanup_robot/`をリポジトリのルートにする。ZIPそのものだけをGitHubに置いても「使用コード一式を置いたリポジトリ」にはしない。
2. GitHubで新規リポジトリを作成し、**VisibilityをPublic**に設定する。既存リポジトリを使う場合もSettingsでPublicを確認する。
3. 展開したファイルをコミットしてpushする。Gitの著者名・メールアドレスに個人情報を出さないよう、GitHubの公開用表示名とnoreplyアドレスを事前に設定する。
4. ログアウト状態またはシークレットウィンドウでリポジトリURLを開き、Public表示、`README.md`、`src/`、`ros/`、`scripts/`、`planner_env/uv.lock`、`uv.lock`が見えることを確認する。モデル重み・生ログ・個人情報がないことも確認する。
5. 確認したGitHub URLと公開commit SHAをWord草稿へ記入し、PDFを書き出す。OmniCampusにはリポジトリURLを提出する。

必要な公開動画はYouTubeへ別途アップロードする。動画をこのコードZIPへ混ぜない。
