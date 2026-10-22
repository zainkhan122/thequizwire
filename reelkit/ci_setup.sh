#!/usr/bin/env bash
# Toolchain for a GitHub Actions ubuntu runner (private repo on GitHub Free: 2 vCPU / 7 GB; public repos get 4 / 16). Node 22 from actions/setup-node.
# NOTE: whisper (faster-whisper) must be fed NumPy arrays, never file paths — its PyAV decoder broke with av ≥ 19 (seen 2026-10-14).
# Cached by actions/cache: ~/.cache/hyperframes (chrome-headless-shell), ~/.cache/pip, ~/.cache/huggingface (whisper),
# ~/.cache/kokoro (TTS model + voices, ~90 MB), ~/.cache/geodata (Natural Earth 50m/10m + disputed areas).
# Idempotent: every step is a no-op when its artefact is already present, so a warm cache finishes in ~1 minute.
set -euo pipefail
HFV="${HYPERFRAMES_VERSION:-0.8.137}"
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1 DO_NOT_TRACK=1 HYPERFRAMES_SKIP_SKILLS=1
C="$HOME/.cache"; mkdir -p "$C"/{kokoro,geodata,build,secrets,tmp}
retry() { local n=0; until "$@"; do n=$((n+1)); [ $n -ge 3 ] && return 1; echo "  … retry $n/2: $*" >&2; sleep $((10*n)); done; }

echo "== ffmpeg (static build, cached — apt on the hosted runners hung 3× on 2026-10-22)"
FF="$C/ffmpeg"; mkdir -p "$FF"
if ! "$FF/ffmpeg" -version >/dev/null 2>&1; then
  if command -v ffmpeg >/dev/null; then ln -sf "$(command -v ffmpeg)" "$FF/ffmpeg"; ln -sf "$(command -v ffprobe)" "$FF/ffprobe"; echo "  runner image ffmpeg: $(ffmpeg -version | head -1)"
  else
    get_ff() { curl -fsSL --retry 3 -m 300 "$1" -o "$C/tmp/ff.tar.xz" && tar -xJf "$C/tmp/ff.tar.xz" -C "$C/tmp" && \
               f=$(find "$C/tmp" -type f -name ffmpeg | head -1) && cp "$f" "$FF/ffmpeg" && cp "$(dirname "$f")/ffprobe" "$FF/ffprobe" && chmod +x "$FF"/ff*; }
    get_ff https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
      || get_ff https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
      || { echo "ci_setup: could not fetch a static ffmpeg" >&2; exit 1; }
    echo "  downloaded $("$FF/ffmpeg" -version | head -1)"
  fi
fi
export PATH="$FF:$PATH"; [ -n "${GITHUB_PATH:-}" ] && echo "$FF" >> "$GITHUB_PATH"

echo "== apt: chrome-headless-shell libs (only what the image lacks)"
APT="-o Acquire::Retries=3 -o Acquire::http::Timeout=30"
PKGS="libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libxdamage1 libxkbcommon0 libasound2t64 libatspi2.0-0t64 libgbm1 \
  libxcomposite1 libxrandr2 libpango-1.0-0 libcairo2 libcups2t64 libdrm2 libxfixes3 fonts-liberation"
MISSING=""; for p in $PKGS; do dpkg -s "$p" >/dev/null 2>&1 || MISSING="$MISSING $p"; done
if [ -z "$MISSING" ]; then echo "  all libs already on the runner image — apt skipped"
else
  echo "  missing:$MISSING"
  export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1
  retry timeout 240 sudo -E apt-get $APT update -qq
  retry timeout 420 sudo -E apt-get $APT install -y -qq --no-install-recommends $MISSING >/dev/null
fi
echo "== hyperframes@$HFV + browser"
retry npm i -g --silent "hyperframes@$HFV" >/dev/null
retry hyperframes browser ensure >/dev/null
# fail fast (seconds) instead of 10 minutes into a render: CLI version pinned, browser binary present
hyperframes --version 2>/dev/null | grep -q "$HFV" || { echo "ci_setup: hyperframes@$HFV not installed" >&2; exit 1; }
ls "$HOME"/.cache/hyperframes/chrome/chrome-headless-shell/*/chrome-headless-shell-linux64/chrome-headless-shell >/dev/null 2>&1 \
  || { echo "ci_setup: chrome-headless-shell missing after 'hyperframes browser ensure'" >&2; exit 1; }


echo "== python deps"
python3 -m pip install -q --upgrade pip >/dev/null 2>&1 || true
# gates: voice/qa (faster-whisper, librosa), provenance (fontTools), score (numpy/scipy/soundfile), snaps/svgraster (pillow), TTS (kokoro-onnx)
PYDEPS="numpy scipy soundfile pillow faster-whisper librosa fonttools kokoro-onnx onnxruntime cairosvg opencv-python-headless"
retry python3 -m pip install -q $PYDEPS 2>/dev/null || retry python3 -m pip install -q --break-system-packages $PYDEPS
python3 -c "import numpy, scipy, soundfile, PIL, faster_whisper, librosa, fontTools, kokoro_onnx" || { echo "ci_setup: Python gate dependencies missing" >&2; exit 1; }

echo "== Kokoro-82M (Apache-2.0) int8 ONNX + voices → ~/.cache/kokoro"
KREL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
get() { [ -s "$2" ] || retry curl -fsSL --retry 3 -o "$2.part" "$1" && { [ -s "$2" ] || mv "$2.part" "$2"; }; }
get "$KREL/kokoro-v1.0.int8.onnx" "$C/kokoro/kokoro-v1.0.int8.onnx"
get "$KREL/voices-v1.0.bin" "$C/kokoro/voices-v1.0.bin"
[ -s "$C/kokoro/voices-v1.0.bin" ] && [ -s "$C/kokoro/kokoro-v1.0.int8.onnx" ] || { echo "ci_setup: Kokoro model files missing" >&2; exit 1; }

echo "== geodata (Natural Earth via world-atlas + NE disputed areas) → ~/.cache/geodata (cached; skipped when warm)"
python3 "$(dirname "$0")/geodata.py" fetch --all || echo "::warning::geodata fetch incomplete — episodes needing 50m/10m will fail the geo stage"

echo "CI_SETUP_DONE nproc=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G node=$(node -v) hf=$(hyperframes --version 2>/dev/null | tail -1) docker=$(command -v docker >/dev/null && echo yes || echo no)"
