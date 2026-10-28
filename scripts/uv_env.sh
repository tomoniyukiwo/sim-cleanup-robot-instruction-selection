# Source this file from the project root: source scripts/uv_env.sh
# Keep the previous pip .venv unchanged.
export UV_PROJECT_ENVIRONMENT="$(pwd)/.venv-uv"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
export CMAKE_POLICY_VERSION_MINIMUM="${CMAKE_POLICY_VERSION_MINIMUM:-3.5}"
export CC="${CC:-gcc}"
export CXX="${CXX:-g++}"
export LIBERO_CONFIG_PATH="${LIBERO_CONFIG_PATH:-$(pwd)/.libero}"
