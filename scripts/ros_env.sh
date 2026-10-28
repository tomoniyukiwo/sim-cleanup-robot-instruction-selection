# Source from bash to select an existing ROS 2 installation; does not install ROS.
if [[ -z "${ROS_DISTRO:-}" ]]; then
  ros_setups=(/opt/ros/*/setup.bash)
  if [[ ${#ros_setups[@]} -ne 1 || ! -f "${ros_setups[0]}" ]]; then
    echo 'Source your chosen ROS 2 first: source /opt/ros/<distro>/setup.bash' >&2
    return 1
  fi
  source "${ros_setups[0]}"
fi
