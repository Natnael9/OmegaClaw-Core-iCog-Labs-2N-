#!/usr/bin/env bash
set -euo pipefail

tmp_channel_file="$(mktemp)"
tmp_py_file="$(mktemp --suffix=.py)"
trap 'rm -f "$tmp_channel_file" "$tmp_py_file"' EXIT

cat >"$tmp_py_file" <<'PY'
import sys

LICENSE_TEXT = """\
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

def require_license_acceptance():
    print(LICENSE_TEXT)
    while True:
        reply = input("Type 'accept' to continue or 'q' to exit: ").strip().lower()
        if reply == "accept":
            return
        if reply == "q":
            sys.exit(1)
        print("You must type 'accept' or 'q'.", file=sys.stderr)

def config_run_mettaclaw(output_path):
    print(" ")
    print("Welcome to Omegaclaw IRC!")
    print(" ")
    require_license_acceptance()

    while True:
        print("Please enter your unique IRC channel. Example: ##MyMeTTa54323")
        channel = input("Enter IRC channel or 'q' to exit: ").strip()

        if channel.lower() == "q":
            sys.exit(1)

        if not channel:
            print("IRC channel is required.", file=sys.stderr)
            continue

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(channel)

        return

if __name__ == "__main__":
    config_run_mettaclaw(sys.argv[1])
PY

python3 "$tmp_py_file" "$tmp_channel_file" </dev/tty

channel="$(cat "$tmp_channel_file")"

read -r -s -p "Please enter LLM token: " token </dev/tty
printf '\n'

if [ -z "$token" ]; then
  echo "Error: Invalid token" >&2
  exit 1
fi

printf '%s\n' \
  '============================================' \
  ' QuakeNet / Omegaclaw instructions' \
  '============================================' \
  'Please go to https://webchat.quakenet.org/' \
  'and enter your name and channel.' \
  '' \
  'Stop omegaclaw:' \
  '  docker stop omegaclaw' \
  '' \
  'Restart omegaclaw:' \
  '  docker start omegaclaw' \
  '' \
  'Examine log file in case or problem:' \
  '  docker logs -f omegaclaw' \
  '' \

docker rm -f omegaclaw 2>/dev/null || true

docker run -d -it \
  --name omegaclaw \
  --user 65534:65534 \
  --security-opt no-new-privileges:true \
  --init \
  --tmpfs /tmp:size=64m,mode=1777 \
  --tmpfs /run:size=16m,mode=755 \
  --tmpfs /var/tmp:size=64m,mode=1777 \
  -e OPENAI_API_KEY="$token" \
  jazzbox35/omegaclaw:test \
  "$channel"
