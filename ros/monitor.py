#!/usr/bin/env python3
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

def main():
    rclpy.init();node=Node('cleanup_monitor')
    def show(msg):
        try:print(json.dumps(json.loads(msg.data),ensure_ascii=False),flush=True)
        except ValueError:print(msg.data,flush=True)
    node.create_subscription(String,'/cleanup/status',show,10)
    node.create_subscription(String,'/cleanup/plan',show,10)
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:node.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
