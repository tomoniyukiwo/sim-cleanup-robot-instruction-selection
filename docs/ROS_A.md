# ROS 2での実行

先に[README](../README.md)のセットアップ手順を完了し、Qwen3.5のモデル資産lockを確認する。ROSはシステムPython、AIはuvのPython 3.12を使用する。

選択方法は起動時の`--selector qwen`または`--selector minilm`で指定する。どちらも`/cleanup/instruction`の同じROSトピックから入力を受け、選択したタスクをSmolVLAで実行する。MiniLMが閾値で保留した場合は操作しない。比較用には`configs/ros_comparison.json`（最大200ステップ、1試行）を使用する。task 7の上限延長には`configs/ros_comparison_300.json`を指定する。

```bash
source /opt/ros/humble/setup.bash
/usr/bin/python3 scripts/run_ros_method_comparison.py
```

このスクリプトは固定した遠回しな指示9件を各モデルへ送信し、各回でシーンを初期化する。結果は`outputs/ros_comparison/<実行ID>/manifest.json`に集計し、各リクエストの動画は`outputs/ros/<実行ID>/demo.mp4`へ保存する。

端末A：`bash scripts/run_ros.sh --config configs/qwen35_fewshot.json --lock models/assets.qwen35.lock.json`

端末B：`source scripts/ros_env.sh`の後、`/usr/bin/python3 ros/monitor.py`

端末C：`source scripts/ros_env.sh`の後、登録タスクに合う文で`ros2 topic pub --once /cleanup/instruction std_msgs/msg/String '{data: "指示"}'`

停止：`ros2 service call /cleanup/pause std_srvs/srv/SetBool '{data: true}'`

再開：`ros2 service call /cleanup/pause std_srvs/srv/SetBool '{data: false}'`

取消：`ros2 service call /cleanup/cancel std_srvs/srv/Trigger '{}'`

停止などは次の操作境界で適用する。モデル読み込みの即時中断は保証しない。結果は`outputs/ros/<実行ID>/`に保存する。`clarify`/`reject`とMiniLMの保留では物理操作と動画生成をしない。各リクエストでシーンを初期化する。選択だけの比較では確認判断を測定したが、ROS上の確認対話、停止再開、再試行の効果は未検証。
