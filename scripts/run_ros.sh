#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source scripts/ros_env.sh
source scripts/uv_env.sh
/usr/bin/python3 -c 'import rclpy; from std_msgs.msg import String; from std_srvs.srv import SetBool, Trigger'
exec /usr/bin/python3 ros/supervisor.py --root "$PWD" "$@"
