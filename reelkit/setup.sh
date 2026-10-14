#!/usr/bin/env bash
# reelkit/setup.sh — idempotent SANDBOX toolkit bootstrap (the light half; CI uses reelkit/ci_setup.sh).
#     source ~/quizwire/reelkit/setup.sh   (or: source ~/quizwire/bootstrap.sh — also wires git + prints the resume pack)
#
# Everything heavy lives in ~/.cache (excluded from workspace snapshots → never blows the 128 MB / 10k-file save budget).
# Re-running only fetches what is missing. The sandbox never renders video; it authors, builds HTML, runs the offline gates
# (plan/geo/build/static/quizlint/geolint/facts/provenance/selftest) and previews maps as PNG (reelkit/geopreview.mjs).
#
#   ~/.cache/kokoro/    Kokoro-82M ONNX int8 + voices (Apache-2.0, CPU TTS)   — only with SETUP_TTS=1 (≈ 90 MB, ~1 min)
#   ~/.cache/geodata/   Natural Earth 50m/10m (world-atlas) + disputed areas  — fetched on first `geodata.py fetch`
#   ~/.cache/build/     every episode build (hf/, geo/, mix.wav, snaps)
#   ~/.cache/tmp/       scratch (NOTE: /tmp is RAM-backed tmpfs here — don't build into it)
set -u
C="$HOME/.cache"; mkdir -p "$C"/{bin,kokoro,geodata,build,secrets,tmp,npm-global}
export PATH="$C/npm-global/bin:$C/bin:$HOME/.local/bin:$PATH"
export NPM_CONFIG_PREFIX="$C/npm-global" NPM_CONFIG_CACHE="$C/npm-cache" PUPPETEER_CACHE_DIR="$C/puppeteer"
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 DO_NOT_TRACK=1 PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR="$C/tmp"
ok(){ printf '  \033[32m✓\033[0m %s\n' "$*"; }; bad(){ printf '  \033[31m✗\033[0m %s\n' "$*"; }
get(){ [ -s "$2" ] || { echo "  ↓ $(basename "$2")"; curl -fsSL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"; }; }
QW="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/4] python packages (offline gates + procedural score)"
PKGS="numpy scipy soundfile pillow"
python3 - <<'EOF' 2>/dev/null || pip install -q --user $PKGS 2>&1 | grep -v "^\s*$" | tail -3
import importlib.util as u, sys
sys.exit(0 if all(u.find_spec(m) for m in ["numpy", "scipy", "soundfile", "PIL"]) else 1)
EOF
python3 -c "import numpy, scipy, soundfile, PIL" 2>/dev/null && ok "pip: $PKGS" || bad "pip: $PKGS"

echo "[2/4] node (map runtime tests + hfstatic + geopreview run on the system node; HyperFrames itself only in CI)"
node -v >/dev/null 2>&1 && ok "node $(node -v)" || bad "node missing (apt/nvm)"

echo "[3/4] Kokoro TTS (optional in the sandbox: SETUP_TTS=1 — CI always has it)"
if [ "${SETUP_TTS:-0}" = "1" ]; then
  python3 -c "import kokoro_onnx" 2>/dev/null || pip install -q --user kokoro-onnx onnxruntime soundfile 2>&1 | tail -1
  get https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx "$C/kokoro/kokoro-v1.0.int8.onnx"
  get https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin "$C/kokoro/voices-v1.0.bin"
  [ -s "$C/kokoro/voices-v1.0.bin" ] && ok "kokoro (am_michael ready: python3 reelkit/tts_kokoro.py --say 'test' --voice am_michael)" || bad kokoro
else
  [ -s "$C/kokoro/voices-v1.0.bin" ] && ok "kokoro cached" || echo "  – kokoro skipped (SETUP_TTS=1 to install; takes are normally made by the CI tts stage)"
fi

echo "[4/4] geodata cache"
if [ -s "$C/geodata/natural-earth/ne_10m_admin_0_disputed_areas.geojson" ]; then ok "geodata cached ($(du -sh "$C/geodata" | cut -f1))"
else echo "  – not cached: python3 $QW/reelkit/geodata.py fetch --all   (≈ 9 MB; the offline fallback is tests/fixtures/ne_disputed_kashmir.geojson via GEO_FIXTURE)"; fi
