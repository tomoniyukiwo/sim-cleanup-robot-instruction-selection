# ROS 2での実行

先に[README](../README.md)の`lock`・`sync`・`check`・`prepare`を完了し、Qwen3.5のモデルlockを確認する。指示選択比較で正しく`execute`された代表例だけ送る。ROSはシステムPython、AIはuvのPython 3.12を使用する。

端末A：`bash scripts/run_ros.sh --config configs/qwen35_fewshot.json --lock models/assets.qwen35.lock.json`

端末B：`source scripts/ros_env.sh`の後、`/usr/bin/python3 ros/monitor.py`

端末C：`source scripts/ros_env.sh`の後、登録タスクに合う文で`ros2 topic pub --once /cleanup/instruction std_msgs/msg/String '{data: "指示"}'`

停止：`ros2 service call /cleanup/pause std_srvs/srv/SetBool '{data: true}'`

再開：`ros2 service call /cleanup/pause std_srvs/srv/SetBool '{data: false}'`

取消：`ros2 service call /cleanup/cancel std_srvs/srv/Trigger '{}'`

停止などは次の操作境界で適用する。モデル読み込みの即時中断は保証しない。結果は`outputs/ros/<実行ID>/`に保存する。`clarify`/`reject`では物理操作と動画生成をしない。各リクエストでシーンを初期化する。確認質問・停止再開・再試行の実測がない間は未検証と記す。
