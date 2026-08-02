#!/usr/bin/env bash
# One-command setup. Run:  ./setup.sh
#
# Why this script exists instead of "python3 -m venv venv":
# on a stock Mac, `python3` is Apple's Python 3.9, which has NO MuJoCo wheel. pip
# silently falls back to building MuJoCo from source and dies with the completely
# unrelated-sounding error "MUJOCO_PATH environment variable is not set". This
# script finds a Python 3.10+ interpreter first and tells you plainly if it can't.

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Looking for Python 3.10 or newer (MuJoCo does not support 3.9)..."
PY=""
for c in python3.13 python3.12 python3.11 python3.10 \
         /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 \
         /opt/homebrew/bin/python3.11 /usr/local/bin/python3.12 python3; do
    if command -v "$c" >/dev/null 2>&1; then
        v=$("$c" -c 'import sys; print("%d%02d" % sys.version_info[:2])' 2>/dev/null || echo 0)
        if [ "$v" -ge 310 ] 2>/dev/null; then
            PY="$c"; break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo "ERROR: no Python 3.10+ found."
    echo "  macOS:  brew install python@3.12"
    echo "  Ubuntu: sudo apt install python3.12 python3.12-venv"
    exit 1
fi

echo "==> Using $($PY -V) at $(command -v "$PY")"
echo "==> Creating venv/"
"$PY" -m venv venv
./venv/bin/pip install --quiet --upgrade pip
echo "==> Installing pinned dependencies (this takes a minute)"
./venv/bin/pip install --quiet -r requirements.txt

echo
echo "==> Verifying"
./venv/bin/python -c "import mujoco, numpy; print('   mujoco', mujoco.__version__, '| numpy', numpy.__version__)"

cat <<'EOF'

Setup complete. Next:

    ./venv/bin/python sim_poc2.py --eval 25      # reliability run, prints success rate
    ./venv/bin/python -m mujoco.viewer --mjcf ufactory_xarm7/cartridge_scene_v2.xml

(Or `source venv/bin/activate` first and just use `python`.)
EOF
