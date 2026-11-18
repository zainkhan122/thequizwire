"""One-off YouTube OAuth device flow for GitHub Actions (owner has no local Python).
Prints the verification URL + code to the job log, polls until the owner approves, then prints the refresh
token ONLY as a sealed box for the agent's one-time public key (AGENT_PUBKEY) — never in clear. The agent decrypts
it in the sandbox and writes the repo secret YT_REFRESH_TOKEN through the GitHub API. Delete after use."""
import os, sys, time, json, base64, urllib.request, urllib.parse
from nacl.public import PublicKey, SealedBox
cid, sec, pub = os.environ["YT_CLIENT_ID"], os.environ["YT_CLIENT_SECRET"], os.environ["AGENT_PUBKEY"]
def post(url, form):
    req = urllib.request.Request(url, urllib.parse.urlencode(form).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    try: r = urllib.request.urlopen(req, timeout=30); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
st, d = post("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": "https://www.googleapis.com/auth/youtube"})
if st != 200: sys.exit(f"device code failed ({st}): {d}")
print(f"\n==== OPEN {d['verification_url']}  ·  CODE {d['user_code']}  ·  expires in {d['expires_in']//60} min ====\n", flush=True)
t0, iv = time.time(), int(d.get("interval", 5))
while time.time() - t0 < int(d["expires_in"]):
    time.sleep(iv)
    st, r = post("https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "device_code": d["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
    if st == 200 and r.get("refresh_token"):
        box = SealedBox(PublicKey(base64.b64decode(pub))).encrypt(r["refresh_token"].encode())
        print("SEALED_REFRESH_TOKEN " + base64.b64encode(box).decode(), flush=True); sys.exit(0)
    if r.get("error") == "slow_down": iv += 5
    elif r.get("error") not in ("authorization_pending", None): sys.exit(f"auth failed: {r}")
    print(f"waiting for approval… {int(time.time()-t0)} s", flush=True)
sys.exit("auth timed out — re-run")
