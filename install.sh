#!/usr/bin/env bash
# FB Ad Library Spy - installer (macOS / Linux / Git Bash)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dst="$HOME/.claude/skills/fb-ad-library-spy"
mkdir -p "$HOME/.claude/skills"
rm -rf "$dst" && cp -R "$here/skills/fb-ad-library-spy" "$dst"
echo "[1/3] Skill copied to $dst"
python3 -m pip install -q -r "$here/requirements.txt"
echo "[2/3] Python packages installed"
python3 -m playwright install chromium
echo "[3/3] Chromium for Playwright installed"
command -v ffmpeg >/dev/null || echo "NOTE: ffmpeg not found - video hook frames will be skipped."
echo "Done. Open Claude Code anywhere and paste an Ad Library link."
