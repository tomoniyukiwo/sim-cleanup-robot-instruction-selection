# 提出資料

`report_qwen35_measured_v5.docx`はQwen3.5選択比較の実測入り草稿で、SmolVLAの直接実行はtask 1〜9で8件成功・1件失敗。ROS統合経路は未測定。改めて生成する場合は`python3 scripts/build_docx.py --config configs/qwen35_fewshot.json --summary outputs/comparison/<実行ID>/summary.json --out submission/report_qwen35_measured.docx`で新しい草稿を作る。既存ファイルは上書きしない。Wordで内容と未記入欄を確認し、指定名のPDFへ書き出す。

`report_data.json`のアカウント名・GitHub URL・YouTube URL・commitは本人が記入する。氏名・所属・メールアドレスを含めない。WordからPDFを書き出す。別途PDF生成スクリプトを使う場合は、`python3 scripts/build_report.py --data submission/report_data.json --font /path/to/Japanese.ttf --out submission/report_final.pdf`とし、日本語TTFとreportlabを別途用意する。フォントは公開用ZIPに含めない。
