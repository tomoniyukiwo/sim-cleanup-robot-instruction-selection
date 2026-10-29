# 提出資料

`report_qwen35_ros_v8.docx`はQwen3.5とMiniLMの指示選択比較、およびROS入力から各モデルの判断に基づき独立に実行した物理試行を反映した編集用草稿。Qwen3.5は一貫成功8/9、MiniLMは7/9。MiniLMのtask 4保留と、両モデルがtask 7を300ステップで再実行しても未達だったことを区別している。停止・再開と再試行の効果は未測定。

新しい草稿を生成する場合は、`python3 scripts/build_docx.py --config configs/qwen35_fewshot.json --summary outputs/comparison/<実行ID>/summary.json --ros-experiment outputs/ros_comparison/<比較実行ID>/manifest.json --out submission/<新しいファイル名>.docx`を使う。既存ファイルは上書きしない。Wordで内容と未記入欄を確認し、指定名のPDFへ書き出す。

`report_data.json`のアカウント名・GitHub URL・YouTube URL・commitは本人が記入する。氏名・所属・メールアドレスを含めない。WordからPDFを書き出す。別途PDF生成スクリプトを使う場合は、`python3 scripts/build_report.py --data submission/report_data.json --font /path/to/Japanese.ttf --out submission/report_final.pdf`とし、日本語TTFとreportlabを別途用意する。フォントは公開用ZIPに含めない。
