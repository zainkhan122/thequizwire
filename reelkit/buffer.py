#!/usr/bin/env python3
"""Buffer dispatcher — queue a rendered episode on every enabled Buffer channel (YouTube · Instagram · Facebook).

  python3 reelkit/buffer.py channels                 # discover org + channels with the API key, write ids into config/publishing.json
  python3 reelkit/buffer.py queue                    # queue depth per channel (scheduled / daily limit)
  python3 reelkit/buffer.py plan     <ep> --media-url URL      # show the exact createPost payloads (no network)
  python3 reelkit/buffer.py dispatch <ep> [<ep>…] [--media-url URL] [--live] [--channels youtube,instagram,facebook,twitter,threads]
  python3 reelkit/buffer.py retry    [--live]        # post what dispatch/pending.json holds, skipping accounts still rate-limited (no call)
  python3 reelkit/buffer.py status   [--refresh]     # ledger view; --refresh pulls each post's status from Buffer

Design (docs/DISTRIBUTION.md):
  • mode addToQueue + schedulingType automatic → Buffer slots the post into the channel's own posting schedule; we never
    pick a time, so the owner's Buffer time slots stay the single source of truth for cadence.
  • The media URL must be public, direct, HTTPS and STABLE — Buffer fetches it when the post goes out (hours/days later).
    reelkit/mediahost.py publishes the MP4 on GitHub Pages and prints that URL; this tool verifies it before any write.
  • Idempotent: dispatch/ledger.json records episode × channel → Buffer post id. Before creating, the dispatcher also
    scans the channel's scheduled/sent posts for the same media URL (reconcile) so a lost response never double-posts.
  • Dry-run by default. --live needs BUFFER_API_KEY (env or ~/.cache/secrets/buffer_token) and config enabled: true.
  • Mutations are never blindly retried: a timeout/5xx after createPost raises Ambiguous and the run stops; the next run
    reconciles first and continues. Rate limits (HTTP 429 / RATE_LIMIT_EXCEEDED) honour Retry-After up to 60 s inline.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config/publishing.json"
LEDGER = ROOT / "dispatch/ledger.json"
LIMITS = ROOT / "dispatch/buffer_limits.json"     # {account: {until, reason, seen}} — a 429 Retry-After is remembered across runs (owner 2026-11-27:
PENDING = ROOT / "dispatch/pending.json"          #   "do not waste API calls, be limit-aware, retry when the limit lifts"); deferred posts wait here
UA = "TheQuizWire-reelkit/1 (+https://github.com/zainkhan122/thequizwire)"

POST_FIELDS = "id channelId status dueAt sentAt createdAt externalLink schedulingType shareMode text assets { source mimeType } error { message supportUrl }"
Q_ACCOUNT = "query { account { id email organizations { id name channelCount } } }"
Q_CHANNELS = "query($org: OrganizationId!) { channels(input: { organizationId: $org }) { id name service serviceId displayName externalLink timezone isDisconnected isLocked isQueuePaused postingSchedule { day paused times } } }"
Q_POSTS = "query($input: PostsInput!, $after: String) { posts(first: 100, after: $after, input: $input) { edges { node { " + POST_FIELDS + " } } pageInfo { hasNextPage endCursor } } }"
Q_POST = "query($input: PostInput!) { post(input: $input) { " + POST_FIELDS + " } }"
Q_LIMITS = "query($input: DailyPostingLimitsInput!) { dailyPostingLimits(input: $input) { channelId isAtLimit limit scheduled sent } }"
M_CREATE = "mutation($input: CreatePostInput!) { createPost(input: $input) { __typename ... on PostActionSuccess { post { " + POST_FIELDS + " } } ... on MutationError { message } } }"


M_DELETE = "mutation($input: DeletePostInput!) { deletePost(input: $input) { __typename ... on MutationError { message } } }"


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cfg(): return json.loads(CFG_PATH.read_text())


def save_cfg(c): CFG_PATH.write_text(json.dumps(c, indent=1, ensure_ascii=False) + "\n")


def token(account="BUFFER_API_KEY", required=True):
    """One Buffer login = one API key = one secret. Several accounts (Buffer Free allows 3 channels per login) are listed in
    config buffer.accounts; each channel remembers the account it was discovered through."""
    t = os.environ.get(account)
    if not t:
        p = Path.home() / f".cache/secrets/{account.lower()}"
        t = p.read_text().strip() if p.exists() else None
    if not t and required: sys.exit(f"buffer: no API key — set {account} (GitHub secret) or ~/.cache/secrets/{account.lower()}")
    return t


def accounts(c): return c["buffer"].get("accounts") or ["BUFFER_API_KEY"]


def present_accounts(c): return [a for a in accounts(c) if token(a, required=False)]


def chan_cfg(c, platform): return c["buffer"]["channels"].get(platform) or {}


def account_of(c, platform):
    """Secret name of the Buffer login that owns this channel; None when unknown (several accounts, channel not yet discovered through any)."""
    acc = chan_cfg(c, platform).get("account")
    return acc or (accounts(c)[0] if len(accounts(c)) == 1 else None)


def org_of(c, platform): return chan_cfg(c, platform).get("organization_id") or c["buffer"].get("organization_id")


def groups(c, platforms):
    """{(account, organization_id): [(platform, channel_id), …]} for the configured channels of these platforms."""
    g = {}
    for p in platforms:
        cid = chan_cfg(c, p).get("buffer_id"); acc = account_of(c, p)
        if cid and acc: g.setdefault((acc, org_of(c, p)), []).append((p, cid))
    return g


def redact(s, t):
    return str(s).replace(t, "•••") if t else str(s)


class BufferError(RuntimeError): pass
class Deferred(BufferError): pass      # try again later (rate limit, 5xx on a query)
# ---------------------------------------------------------------- limit memory + pending queue (no network)
def limits_load():
    try: return json.loads(LIMITS.read_text()) if LIMITS.exists() else {}
    except ValueError: return {}


def limit_set(account, seconds, reason):
    """Remember that `account` answered a rate limit: no request goes to it before now+seconds (clamped 60 s … 10 days)."""
    L = limits_load(); until = datetime.now(timezone.utc) + timedelta(seconds=max(60.0, min(float(seconds), 10 * 86400)))
    L[account] = {"until": until.isoformat(timespec="seconds"), "reason": str(reason)[:200], "seen": now()}
    LIMITS.parent.mkdir(parents=True, exist_ok=True); LIMITS.write_text(json.dumps(L, indent=1) + "\n")


def limit_clear(account):
    L = limits_load()
    if account in L: L.pop(account); LIMITS.write_text(json.dumps(L, indent=1) + "\n")


def blocked(account):
    """Human reason if this account is still inside a remembered rate-limit window, else None. Costs no API call."""
    e = limits_load().get(account)
    if not e: return None
    try: until = datetime.fromisoformat(e["until"])
    except Exception: return None
    left = (until - datetime.now(timezone.utc)).total_seconds()
    if left <= 0: return None
    h = left / 3600
    return f"rate limited until {e['until']} ({h:.1f} h left) — no call made"


def pending_load():
    try: return json.loads(PENDING.read_text()) if PENDING.exists() else {"version": 1, "rows": []}
    except ValueError: return {"version": 1, "rows": []}


def pending_save(P):
    PENDING.parent.mkdir(parents=True, exist_ok=True); PENDING.write_text(json.dumps(P, indent=1, ensure_ascii=False) + "\n")


def pending_add(P, episode, ep_dir, platform, account, media_url, payload, reason):
    """Queue one episode × channel for a later `buffer.py retry` (idempotent on episode × platform). The payload is stored
    whole so the retry needs neither the render nor postkit — only the hosted media URL, which stays live until posted."""
    for r in P["rows"]:
        if r["episode"] == episode and r["platform"] == platform:
            r.update({"reason": str(reason)[:200], "last_try": now(), "tries": int(r.get("tries", 0)) + 1, "media_url": media_url, "payload": payload}); return r
    r = {"episode": episode, "ep_dir": str(ep_dir), "platform": platform, "account": account, "media_url": media_url, "payload": payload,
         "reason": str(reason)[:200], "queued_at": now(), "last_try": now(), "tries": 1}
    P["rows"].append(r); return r


def pending_drop(P, episode, platform):
    P["rows"] = [r for r in P["rows"] if not (r["episode"] == episode and r["platform"] == platform)]


def yt_direct_available():
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def yt_direct(ep_dir, media_url, when):
    """YouTube Data API upload (reelkit/yt_enrich.py upload) when Buffer's YouTube account is rate-limited: YouTube keeps
    flowing on its own quota (owner 2026-11-27: "YT is okay, keep sharing to YT"). Returns True when the ledger row was written."""
    import subprocess
    cmd = [sys.executable, str(ROOT / "reelkit/yt_enrich.py"), "upload", str(ep_dir), "--media-url", media_url, "--publish-at", when.strftime("%Y-%m-%dT%H:%M:%SZ")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()
    for l in tail[-4:]: print("      " + l)
    return r.returncode == 0


class Ambiguous(BufferError): pass     # a mutation may have landed: reconcile before retrying
class Rejected(BufferError): pass      # Buffer refused the input deterministically (nothing was created): fix the payload, rerun


class Client:
    def __init__(self, c, account="BUFFER_API_KEY"):
        self.c, self.account_name, self.key = c, account, token(account)
        self.endpoint = c["buffer"].get("endpoint", "https://api.buffer.com")
        self.spacing = float(c["buffer"].get("request_spacing_seconds", 2.0)); self.last = 0.0
        self.attempts = int(c["buffer"].get("max_attempts", 4)); self.n = 0

    def _post(self, body):
        wait = self.spacing - (time.monotonic() - self.last)
        if wait > 0: time.sleep(wait)
        self.last = time.monotonic(); self.n += 1
        req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as r: return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def gql(self, query, variables=None, mutation=False):
        for attempt in range(self.attempts):
            try:
                status, headers, raw = self._post({"query": query, "variables": variables or {}})
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if mutation: raise Ambiguous(f"transport error after createPost: {e}")
                if attempt + 1 == self.attempts: raise Deferred(f"Buffer unreachable: {e}")
                time.sleep(min(2 ** (attempt + 1), 30)); continue
            if status == 429:
                ra = headers.get("Retry-After") or headers.get("retry-after") or "30"
                wait = float(ra) if re.fullmatch(r"[\d.]+", ra) else 60.0
                if wait > 480 or attempt + 1 == self.attempts:
                    limit_set(self.account_name, wait if wait > 480 else 900, f"HTTP 429 Retry-After {wait:.0f}s")      # remembered: later runs skip this account without a call
                    raise Deferred(f"rate limited; retry after {wait:.0f}s")
                print(f"   (Buffer rate limit on {self.account_name}: sleeping {wait:.0f}s)", flush=True); time.sleep(wait + 1); continue
            if status in (401, 403): raise BufferError("Buffer rejected the API key (401/403) — rotate BUFFER_API_KEY")
            if status >= 500:
                if mutation: raise Ambiguous(f"HTTP {status} after createPost — reconcile before retrying")
                if attempt + 1 == self.attempts: raise Deferred(f"Buffer HTTP {status}")
                time.sleep(min(2 ** (attempt + 1), 30)); continue
            if status != 200: raise BufferError(f"Buffer HTTP {status}: {redact(raw[:300], self.key)}")
            try: body = json.loads(raw)
            except ValueError:
                if mutation: raise Ambiguous("unreadable createPost response — reconcile before retrying")
                raise Deferred("unreadable Buffer response")
            errs = body.get("errors") or []
            if errs:
                codes = {(e.get("extensions") or {}).get("code", "UNKNOWN") for e in errs}
                msg = "; ".join(e.get("message", "") for e in errs)[:300]
                data = body.get("data") or {}
                if mutation and ((data.get("createPost") or {}).get("post") or {}).get("id"): return data
                if codes <= {"RATE_LIMIT_EXCEEDED"}:
                    if attempt + 1 < self.attempts: time.sleep(30); continue
                    limit_set(self.account_name, 3600, "GraphQL RATE_LIMIT_EXCEEDED"); raise Deferred("rate limited (RATE_LIMIT_EXCEEDED); retry in 1 h")
                if codes & {"UNAUTHORIZED", "FORBIDDEN"}: raise BufferError(f"Buffer auth error: {msg}")
                if codes <= {"GRAPHQL_VALIDATION_FAILED", "BAD_USER_INPUT"}: raise BufferError(f"GraphQL input rejected: {msg}")
                if mutation: raise Ambiguous(f"uncertain createPost outcome ({','.join(sorted(codes))}): {msg}")
                raise Deferred(f"Buffer query failed ({','.join(sorted(codes))}): {msg}")
            if not isinstance(body.get("data"), dict):
                if mutation: raise Ambiguous("createPost returned no data — reconcile before retrying")
                raise Deferred("Buffer returned no data")
            if self.n == 1 and limits_load().get(self.account_name): limit_clear(self.account_name)   # the window has passed and the account answers again
            return body["data"]
        raise Deferred("retry budget exhausted")

    # ---- queries
    def account(self): return self.gql(Q_ACCOUNT)["account"]

    def channels(self, org): return self.gql(Q_CHANNELS, {"org": org})["channels"]

    def posts(self, org, channel_ids, statuses, max_pages=6, since_days=None):
        """Posts of these channels/statuses, newest first. since_days bounds the scan (Buffer's startDate = createdAt or dueAt
        on/after that date) so channels with years of history stay cheap and complete."""
        flt = {"channelIds": channel_ids, "status": statuses}
        if since_days: flt["startDate"] = (datetime.now(timezone.utc) - timedelta(days=int(since_days))).isoformat(timespec="seconds")
        inp = {"organizationId": org, "filter": flt, "sort": [{"field": "createdAt", "direction": "desc"}]}
        out, after = [], None
        for _ in range(max_pages):
            page = self.gql(Q_POSTS, {"input": inp, "after": after})["posts"]
            out += [e["node"] for e in page.get("edges") or []]
            if not page["pageInfo"]["hasNextPage"]: return out, True
            after = page["pageInfo"]["endCursor"]
        return out, False

    def post(self, pid): return self.gql(Q_POST, {"input": {"id": pid}})["post"]

    def limits(self, channel_ids): return self.gql(Q_LIMITS, {"input": {"channelIds": channel_ids}})["dailyPostingLimits"]

    def delete(self, pid):
        res = self.gql(M_DELETE, {"input": {"id": pid}}).get("deletePost") or {}
        if res.get("message"): raise BufferError(f"deletePost {pid}: {res['message']}")
        return True

    def create(self, payload):
        res = self.gql(M_CREATE, {"input": payload}, mutation=True).get("createPost") or {}
        if (res.get("post") or {}).get("id"): return res["post"]
        kind, msg = res.get("__typename", "Unknown"), res.get("message", "")
        if kind in ("LimitReachedError", "PostLimitReachedError"): raise Deferred(f"posting limit reached: {msg}")
        if kind in ("InvalidInputError", "PostInvalidInputError", "UnauthorizedError", "NotFoundError", "PostChannelNotFoundError", "DuplicateError", "ChannelRefreshRequired"):
            raise Rejected(f"{kind}: {msg}")
        raise Ambiguous(f"{kind}: {msg or 'unknown createPost result'}")


# ---------------------------------------------------------------- ledger
def load_ledger():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {"version": 1, "posts": []}


def save_ledger(L):
    LEDGER.parent.mkdir(parents=True, exist_ok=True); LEDGER.write_text(json.dumps(L, indent=1, ensure_ascii=False) + "\n")


def ledger_entry(L, ep, platform):
    for p in L["posts"]:
        if p["episode"] == ep and p["platform"] == platform and p.get("state") not in ("error", "abandoned"): return p
    return None


# ---------------------------------------------------------------- best-time scheduling
def best_slot(c, platform, channel_id, taken, start=None):
    """Next free best-performing slot for this channel (config buffer.scheduling): the per-platform local times in the
    audience timezone, from `min_lead_minutes` ahead, skipping any time already holding a scheduled/sent post (`taken` =
    set of ISO minutes per channel, from the Buffer scan + this run). Returns an aware UTC datetime, or None (= queue)."""
    from zoneinfo import ZoneInfo
    S = c["buffer"].get("scheduling") or {}
    if S.get("mode") != "best_times": return None
    tz = ZoneInfo(S.get("audience_tz", "America/New_York")); times = S.get("times", {}).get(platform) or S.get("times", {}).get("default") or []
    if not times: return None
    t0 = (start or datetime.now(timezone.utc)) + timedelta(minutes=int(S.get("min_lead_minutes", 90)))
    day = t0.astimezone(tz).date()
    for d in range(0, 21):
        for hm in sorted(times):
            h, m = (int(x) for x in hm.split(":"))
            cand = datetime(day.year, day.month, day.day, h, m, tzinfo=tz) + timedelta(days=d)
            cand_utc = cand.astimezone(timezone.utc)
            if cand_utc < t0: continue
            key = (channel_id, cand_utc.strftime("%Y-%m-%dT%H:%M"))
            if key in taken: continue
            if any(k[0] == channel_id and abs((datetime.strptime(k[1], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc) - cand_utc).total_seconds()) < 3600 * int(S.get("min_gap_hours", 3)) for k in taken): continue
            taken.add(key); return cand_utc
    return None


def taken_slots(existing, ledger):
    T = set()
    for p in existing:
        if p.get("dueAt") and p.get("status") in ("scheduled", "sending", "sent"): T.add((p["channelId"], p["dueAt"][:16]))
    for p in ledger.get("posts", []):
        if p.get("due_at") and p.get("state") in ("scheduled", "sending", "sent"): T.add((p.get("channel_id"), p["due_at"][:16]))
    return T


# ---------------------------------------------------------------- payloads
def payloads(c, ep_dir, media_url, kit=None, channels=None):
    ep_dir = Path(ep_dir)
    kit = kit or json.loads((ep_dir / "out/postkit.json").read_text())
    want = channels or [p for p, ch in c["buffer"]["channels"].items() if ch.get("enabled")]
    rows = []
    for platform in want:
        ch = c["buffer"]["channels"].get(platform) or {}
        base = {"channelId": ch.get("buffer_id") or f"<{platform} channel id — run buffer.py channels>",
                "mode": c["buffer"].get("mode", "addToQueue"), "schedulingType": c["buffer"].get("scheduling_type", "automatic"),
                "needsApproval": False, "aiAssisted": False, "source": "thequizwire-reelkit"}
        if platform == "youtube":
            y = kit["youtube"]
            base.update({"text": y["description"], "assets": [{"video": {"url": media_url, "metadata": {"title": y["title"]}}}],
                         "metadata": {"youtube": {"title": y["title"], "categoryId": y["categoryId"], "privacy": y["privacy"], "madeForKids": y["madeForKids"],
                                                  "notifySubscribers": y["notifySubscribers"], "embeddable": y["embeddable"], "license": y["license"], "isAiGenerated": y["isAiGenerated"]}}})
        elif platform == "instagram":
            g = kit["instagram"]
            base.update({"text": g["caption"], "assets": [{"video": {"url": media_url, "metadata": {"thumbnailOffset": int(g.get("thumbnailOffsetMs", 0))}}}],
                         "metadata": {"instagram": {"type": "reel", "shouldShareToFeed": bool(g["shouldShareToFeed"]), "isAiGenerated": bool(g["isAiGenerated"]),
                                                    **({"firstComment": g["firstComment"]} if g.get("firstComment") else {})}}})
        elif platform == "facebook":
            f = kit["facebook"]
            base.update({"text": f["text"], "assets": [{"video": {"url": media_url}}],
                         "metadata": {"facebook": {"type": "reel", **({"firstComment": f["firstComment"]} if f.get("firstComment") else {})}}})
        elif platform == "threads":                                           # Threads: text ≤ 500 + video; one topic tag
            th = kit["threads"]
            base.update({"text": th["text"], "assets": [{"video": {"url": media_url}}]})
        elif platform == "twitter":                                           # X: single post + video; thread not needed
            x = kit["twitter"]
            base.update({"text": x["text"], "assets": [{"video": {"url": media_url}}],
                         "metadata": {"twitter": {"isAiGenerated": bool(x.get("isAiGenerated", True))}}})
        else:
            raise SystemExit(f"buffer: unsupported platform {platform}")
        rows.append({"platform": platform, "payload": base})
    return rows


def verify_media(url):
    """Public · direct · HTTPS · video/mp4 · starts with an MP4 'ftyp' box. Fails loudly: Buffer would fail silently at publish time."""
    if not url.startswith("https://"): raise SystemExit(f"media url must be https: {url}")
    req = urllib.request.Request(url, headers={"Range": "bytes=0-1023", "User-Agent": UA})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as r:
            status, ctype, head = r.status, r.headers.get("Content-Type", ""), r.read(1024)
            total = r.headers.get("Content-Range", "").rsplit("/", 1)[-1] if r.status == 206 else r.headers.get("Content-Length", "")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"media url not public/direct (HTTP {e.code}): {url}")
    if status not in (200, 206): raise SystemExit(f"media url HTTP {status}: {url}")
    if ctype.split(";")[0].strip() != "video/mp4": raise SystemExit(f"media url is not video/mp4 ({ctype}): {url}")
    if len(head) < 12 or head[4:8] != b"ftyp": raise SystemExit("media url does not serve an MP4 (no ftyp box)")
    return int(total) if str(total).isdigit() else None


# ---------------------------------------------------------------- commands
def cmd_channels(a):
    c = cfg(); found = []                                                     # (account, org_id, channel)
    before = json.dumps(c["buffer"]["channels"], sort_keys=True)
    present = present_accounts(c); unavailable = []
    if not present: sys.exit(f"buffer: none of {accounts(c)} is set")
    for acc in present:
        if blocked(acc): print(f"   ({acc}: {blocked(acc)} — keeping its channels from config)"); unavailable.append(acc); continue
        cl = Client(c, acc)
        try: acct = cl.account()
        except Deferred as e:                                                   # 11-19: BUFFER_API_KEY_2 answered 429 Retry-After 9.5 days; discovery must not sink the whole preflight
            print(f"::warning::buffer: {acc} unavailable ({e}) — keeping its channels from config; dispatch will defer them"); unavailable.append(acc); continue
        orgs = acct.get("organizations") or []
        if not orgs: print(f"buffer: {acc} ({acct.get('email')}) sees no organization"); continue
        for o in orgs:
            chans = cl.channels(o["id"])
            print(f"account {acct['email']} ({acc}) · organization {o['id']} {o.get('name') or ''} · {len(chans)} channel(s)")
            for ch in chans:
                flags = " ".join(f for f, on in (("DISCONNECTED", ch["isDisconnected"]), ("LOCKED", ch["isLocked"]), ("QUEUE-PAUSED", ch["isQueuePaused"])) if on)
                slots = sum(len(d["times"]) for d in ch.get("postingSchedule") or [] if not d.get("paused"))
                print(f"   {ch['service']:<10} {ch['id']}  {ch['name']!r:<32} tz {ch['timezone']}  {slots} slots/week  {flags}")
                found.append((acc, o["id"], ch))
    missing = [a for a in accounts(c) if a not in present]
    if missing: print(f"buffer: account secret(s) not set in this environment: {', '.join(missing)} — their channels cannot be discovered")
    c["buffer"]["organization_id"] = found[0][1] if found else c["buffer"].get("organization_id", "")
    for platform, entry in c["buffer"]["channels"].items():
        vis = [(acc, org, ch) for acc, org, ch in found if ch["id"] == entry.get("buffer_id")]
        if entry.get("buffer_id") and vis:
            acc, org, ch = vis[0]; entry.update({"account": acc, "organization_id": org}); continue   # pinned and still visible
        if entry.get("buffer_id"):
            if missing or entry.get("account") in unavailable: print(f"   {platform}: channel {entry['buffer_id']} not visible right now — keeping it"); continue
            print(f"   {platform}: previous channel {entry['buffer_id']} is no longer visible — clearing"); entry.update({"buffer_id": "", "service_id": "", "name": "", "account": "", "organization_id": ""})
        hits = [(acc, org, ch) for acc, org, ch in found if ch["service"] == platform and not ch["isDisconnected"]]
        if len(hits) == 1:
            acc, org, ch = hits[0]; entry.update({"buffer_id": ch["id"], "service_id": ch["serviceId"], "name": ch["name"], "account": acc, "organization_id": org})
        elif len(hits) > 1:
            print(f"   ! {platform}: {len(hits)} channels — set buffer.channels.{platform}.buffer_id (+ account, organization_id) by hand")
        else:
            print(f"   ! {platform}: no connected channel in {'any account' if len(present) > 1 else present[0]}")
    if json.dumps(c["buffer"]["channels"], sort_keys=True) == before:
        print("buffer: channel ids unchanged"); return
    c["buffer"]["discovered_at"] = now(); save_cfg(c)
    print(f"buffer: config/publishing.json updated (ids only — commit it)")


def cmd_queue(a):
    c = cfg(); want = [p for p, ch in c["buffer"]["channels"].items() if ch.get("enabled")]
    g = groups(c, want)
    if not g: sys.exit("buffer: no channel ids — run `buffer.py channels` first")
    for p in want:
        if chan_cfg(c, p).get("buffer_id") and not account_of(c, p): print(f"   {p:<10} account unknown — run `buffer.py channels` with every key present")
    for (acc, org), items in g.items():
        if not token(acc, required=False): print(f"   ({acc} not set — {', '.join(p for p, _ in items)} not checked)"); continue
        if blocked(acc): print(f"   ({acc}: {blocked(acc)} — {', '.join(p for p, _ in items)} not checked)"); continue
        cl = Client(c, acc); ids = [cid for _, cid in items]
        try:
            sched, complete = cl.posts(org, ids, ["scheduled", "sending"])
            lim = {l["channelId"]: l for l in cl.limits(ids)}
        except Deferred as e:
            print(f"::warning::buffer: {acc} unavailable ({e}) — {', '.join(p for p, _ in items)} not checked"); continue
        for p, cid in items:
            n = sum(1 for x in sched if x["channelId"] == cid); l = lim.get(cid, {})
            print(f"   {p:<10} queued {n:>3}{'' if complete else '+'}   today: scheduled {l.get('scheduled', '?')} sent {l.get('sent', '?')} limit {l.get('limit', '—')}{'  AT LIMIT' if l.get('isAtLimit') else ''}")


def cmd_plan(a):
    c = cfg(); rows = payloads(c, a.episode, a.media_url, channels=a.channels.split(",") if a.channels else None)
    print(json.dumps(rows, indent=1, ensure_ascii=False))


def _create_rows(c, L, P, clients, existing, lim, down, taken, jobs, live, no_verify=False, retry=False):
    """Shared by dispatch and retry: for every (episode, channel) row create the Buffer post, or queue it in pending.json
    with the reason. A channel whose Buffer account is rate-limited gets no API call; YouTube falls back to a direct
    Data-API upload when the OAuth secrets are present. Returns (created, skipped, failed, deferred)."""
    cap = int(c["buffer"].get("queue_limit_per_channel", 14)); T = dict(created=0, skipped=0, failed=0, deferred=0)
    for name, ep_dir, kit, media_url, rows in jobs:
        print(f"== {name}")
        if no_verify and not live: print(f"   media (unverified, dry-run): {media_url}")
        else:
            try: size = verify_media(media_url); print(f"   media ok: {media_url} ({(size or 0) / 1e6:.1f} MB)")
            except SystemExit as e:
                print(f"   media gone: {e}")
                for r in rows: pending_drop(P, name, r["platform"])
                T["failed"] += 1; continue
        created = skipped = failed = deferred = 0
        for r in rows:
            platform, payload = r["platform"], r["payload"]
            prev = ledger_entry(L, name, platform)
            if prev:
                print(f"   {platform:<10} already queued as {prev['post_id']} ({prev['state']}) — skip"); pending_drop(P, name, platform); skipped += 1; continue
            acc = account_of(c, platform)
            slot = best_slot(c, platform, payload["channelId"], taken)
            if slot: payload["mode"] = "customScheduled"; payload["dueAt"] = slot.strftime("%Y-%m-%dT%H:%M:%SZ")
            else: payload.pop("dueAt", None); payload["mode"] = c["buffer"].get("mode", "addToQueue")
            if not live:
                print(f"   {platform:<10} DRY-RUN would create {payload['mode']} post{' at ' + payload['dueAt'] if slot else ''} · text {len(payload['text'])} chars · channel {payload['channelId']} · via {acc or 'account unknown'}"); continue

            def defer(reason):
                nonlocal deferred
                if platform == "youtube" and yt_direct_available() and ep_dir and Path(ep_dir).exists():
                    print(f"   {platform:<10} Buffer unavailable ({reason}) → direct YouTube upload")
                    when = slot or (datetime.now(timezone.utc) + timedelta(minutes=int((c["buffer"].get("scheduling") or {}).get("min_lead_minutes", 90))))
                    if yt_direct(ep_dir, media_url, when):
                        L.update(load_ledger()); pending_drop(P, name, platform); print(f"   {platform:<10} uploaded directly (YouTube Data API) · publishAt {when.strftime('%Y-%m-%dT%H:%M:%SZ')}"); return True
                    print(f"   {platform:<10} direct upload failed — kept in pending")
                pending_add(P, name, ep_dir, platform, acc, media_url, payload, reason)
                print(f"   {platform:<10} deferred: {reason} → dispatch/pending.json (retried by publish-sync)"); deferred += 1; return False

            if acc not in clients or acc in down:
                if defer('channel account unknown' if not acc else down.get(acc) or acc + ' secret not set'): created += 1
                continue
            same = [p for p in existing if p["channelId"] == payload["channelId"] and any(x.get("source") == media_url for x in p.get("assets") or [])]
            if same:                                                                   # a lost response from an earlier run: adopt it
                p = same[0]; print(f"   {platform:<10} found existing post {p['id']} ({p['status']}) with this media — adopting")
                L["posts"].append({"episode": name, "platform": platform, "post_id": p["id"], "channel_id": payload["channelId"], "state": p["status"],
                                   "media_url": media_url, "due_at": p.get("dueAt"), "created_at": p.get("createdAt"), "recorded_at": now(), "adopted": True, "account": acc})
                save_ledger(L); pending_drop(P, name, platform); skipped += 1; continue
            queued = sum(1 for p in existing if p["channelId"] == payload["channelId"] and p["status"] in ("scheduled", "sending"))
            queued += sum(1 for p in L["posts"] if p.get("channel_id") == payload["channelId"] and p.get("state") == "scheduled" and p.get("recorded_at", "") > (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
            if queued >= cap:
                defer(f"queue has {queued} posts (cap {cap})"); continue
            if lim.get(payload["channelId"], {}).get("isAtLimit"):
                defer("Buffer daily posting limit reached"); continue
            try:
                p = clients[acc].create(payload)
            except Ambiguous as e:
                L["posts"].append({"episode": name, "platform": platform, "post_id": None, "channel_id": payload["channelId"], "state": "ambiguous",
                                   "media_url": media_url, "recorded_at": now(), "error": str(e), "account": acc}); save_ledger(L); pending_save(P)
                sys.exit(f"buffer: {platform}: {e} — ledger marked ambiguous; rerun reconciles before creating again")
            except Deferred as e:
                down[acc] = str(e)
                if defer(str(e)): created += 1
                continue
            except Rejected as e:                                                      # nothing created; other channels go on; exit 1 at the end
                print(f"   {platform:<10} REJECTED: {e}")
                L["posts"].append({"episode": name, "platform": platform, "post_id": None, "channel_id": payload["channelId"], "state": "error",
                                   "media_url": media_url, "recorded_at": now(), "error": str(e)[:300], "account": acc}); save_ledger(L); pending_drop(P, name, platform); failed += 1; continue
            L["posts"].append({"episode": name, "platform": platform, "post_id": p["id"], "channel_id": payload["channelId"], "state": p["status"],
                               "media_url": media_url, "due_at": p.get("dueAt"), "created_at": p.get("createdAt"), "recorded_at": now(),
                               "title": (kit or {}).get("youtube", {}).get("title") if platform == "youtube" else None, "account": acc, **({"retried": True} if retry else {})})
            save_ledger(L); pending_drop(P, name, platform); created += 1
            print(f"   {platform:<10} queued → post {p['id']} · status {p['status']} · due {p.get('dueAt') or 'next free slot'}")
        print(f"buffer: {name} · {'LIVE' if live else 'dry-run'} · created {created} · skipped {skipped} · rejected {failed} · deferred {deferred}")
        for k, v in (("created", created), ("skipped", skipped), ("failed", failed), ("deferred", deferred)): T[k] += v
    pending_save(P)
    return T


def _scan_accounts(c, plats, live, clients, existing, lim, down):
    """One post scan + limits query per Buffer account that is not inside a remembered rate-limit window."""
    if not live: return
    for (acc, org), items in groups(c, plats).items():
        why = blocked(acc)
        if why: down[acc] = why; print(f"   ({acc}: {why} — its channels wait in pending.json)"); continue
        if not token(acc, required=False): down[acc] = f"{acc} secret not set"; print(f"   ({acc} secret not set — its channels are deferred)"); continue
        cl = clients[acc] = clients.get(acc) or Client(c, acc); gids = [cid for _, cid in items]
        win = int(c["buffer"].get("dedupe_window_days", 14))                       # a lost createPost response is minutes old, not months
        try:
            ex, complete = cl.posts(org, gids, ["scheduled", "sending", "sent", "needs_approval", "draft"], max_pages=10, since_days=win)
            if not complete: sys.exit(f"buffer: post scan incomplete (> 1000 posts in {win} days) — refusing to risk a duplicate; lower buffer.dedupe_window_days")
            existing += ex; lim.update({l["channelId"]: l for l in cl.limits(gids)})
        except Deferred as e:                                                      # this account is unavailable right now: defer its channels
            down[acc] = str(e); print(f"   ({acc}: {e} — its channels are deferred to pending.json)")


def cmd_dispatch(a):
    """Queue one or more episodes. Several episodes share ONE post scan + limits query per Buffer account (rate limits are tight
    on Free plans); each episode's media URL comes from --media-url (single episode) or <ep>/out/media_url.txt.
    Channels that cannot be posted now (account rate-limited · queue cap · daily limit) go to dispatch/pending.json and are
    retried by `buffer.py retry` (publish-sync, 3×/day) without re-rendering; YouTube falls back to a direct upload."""
    c = cfg()
    if not c.get("enabled"): sys.exit("buffer: config/publishing.json enabled=false")
    if a.media_url and len(a.episode) != 1: sys.exit("buffer: --media-url needs exactly one episode")
    want = a.channels.split(",") if a.channels else None
    jobs = []                                                                          # (name, ep_dir, kit, media_url, rows)
    for e in a.episode:
        ep = Path(e); kit_p = ep / "out/postkit.json"
        if not kit_p.exists(): sys.exit(f"buffer: {kit_p} missing — run reelkit/postkit.py build first")
        kit = json.loads(kit_p.read_text())
        if kit.get("checks", {}).get("fail"): sys.exit(f"buffer: {ep.name}: postkit has FAILs: {kit['checks']['fail']}")
        url = a.media_url or ((ep / "out/media_url.txt").read_text().strip() if (ep / "out/media_url.txt").exists() else "")
        if not url: sys.exit(f"buffer: {ep.name}: no media url (--media-url or out/media_url.txt from mediahost.py push)")
        jobs.append((ep.name, str(ep), kit, url, payloads(c, ep, url, kit, want)))
    live = a.live and not a.dry_run
    L = load_ledger(); P = pending_load(); clients, existing, lim, down = {}, [], {}, {}
    if live:
        ids = [r["payload"]["channelId"] for *_, rows in jobs for r in rows]
        if any(i.startswith("<") for i in ids): sys.exit("buffer: channel ids missing — run `buffer.py channels`")
        _scan_accounts(c, sorted({r["platform"] for *_, rows in jobs for r in rows}), live, clients, existing, lim, down)
    taken = taken_slots(existing, L)
    T = _create_rows(c, L, P, clients, existing, lim, down, taken, jobs, live, no_verify=a.no_verify)
    if len(jobs) > 1: print(f"buffer: {len(jobs)} episode(s) · created {T['created']} · rejected {T['failed']} · deferred {T['deferred']}" + (f" · unavailable accounts: {', '.join(down)}" if down else ""))
    if T["failed"]: sys.exit(1)


def cmd_retry(a):
    """Post what earlier runs had to defer (dispatch/pending.json). Accounts still inside their remembered rate-limit window
    are skipped WITHOUT a request; the rest get one scan + create per row. Runs from publish-sync 3×/day, so a lifted limit
    is used within hours. Rows whose media is gone or whose episode already has a ledger post are dropped."""
    c = cfg(); P = pending_load()
    want = set(a.channels.split(",")) if a.channels else None
    rows = [r for r in P["rows"] if not want or r["platform"] in want]
    if not rows: print("buffer retry: nothing pending"); return
    live = a.live and not a.dry_run
    by_ep = {}
    for r in rows: by_ep.setdefault((r["episode"], r.get("ep_dir"), r["media_url"]), []).append({"platform": r["platform"], "payload": dict(r["payload"])})
    jobs = [(name, ep_dir, None, url, rs) for (name, ep_dir, url), rs in by_ep.items()]
    plats = sorted({r["platform"] for r in rows})
    accts = {account_of(c, p) for p in plats}
    waiting = {acc: blocked(acc) for acc in accts if acc and blocked(acc)}
    for acc, why in waiting.items(): print(f"   ({acc}: {why})")
    if live and len(waiting) == len([x for x in accts if x]) and not (yt_direct_available() and "youtube" in plats):
        print(f"buffer retry: every account is rate-limited — {len(rows)} row(s) wait (no API call made)"); return
    L = load_ledger(); clients, existing, lim, down = {}, [], {}, {}
    _scan_accounts(c, plats, live, clients, existing, lim, down)
    taken = taken_slots(existing, L)
    T = _create_rows(c, L, P, clients, existing, lim, down, taken, jobs, live, retry=True)
    left = len(pending_load()["rows"])
    print(f"buffer retry: {len(rows)} row(s) · created {T['created']} · rejected {T['failed']} · still pending {left}")
    if T["failed"]: sys.exit(1)


def cmd_status(a):
    c = cfg(); L = load_ledger()
    if a.refresh:
        clients = {}; skipped_acc = set()
        for p in L["posts"]:
            if p.get("post_id") and p.get("state") not in ("sent",):
                acc = p.get("account") or account_of(c, p["platform"])
                if acc == "YT_OAUTH" or str(p.get("post_id", "")).startswith("yt:"): continue          # direct YouTube uploads are not Buffer posts
                if not token(acc, required=False): p["refresh_error"] = f"{acc} not set"; continue
                if blocked(acc): skipped_acc.add(acc); continue                                          # no call inside a remembered rate-limit window
                cl = clients[acc] = clients.get(acc) or Client(c, acc)
                try:
                    q = cl.post(p["post_id"]); p.update({"state": q["status"], "due_at": q.get("dueAt"), "sent_at": q.get("sentAt"), "external_link": q.get("externalLink"), "refreshed_at": now()})
                    if q.get("error"): p["error"] = q["error"].get("message")
                except Deferred as e:
                    p["refresh_error"] = str(e); skipped_acc.add(acc)                                     # the 429 is now remembered; later posts of this account are skipped
                except BufferError as e:
                    p["refresh_error"] = str(e)
        for acc in skipped_acc: print(f"   ({acc}: {blocked(acc) or 'unavailable'} — its posts were not refreshed)")
        save_ledger(L)
    for p in L["posts"]:
        print(f"   {p['episode']:<44} {p['platform']:<10} {str(p.get('state')):<12} {p.get('post_id') or '—':<26} due {p.get('due_at') or '—'}  {p.get('external_link') or ''}")
    print(f"ledger: {len(L['posts'])} record(s)")


def cmd_recopy(a):
    """Replace the text of every still-SCHEDULED post of an episode with the current postkit copy: delete + re-create at the
    same dueAt on the same channel (Buffer's API has no updatePost). Sent posts are reported, not touched."""
    c = cfg(); L = load_ledger(); live = a.live
    for e in a.episode:
        ep = Path(e); name = ep.name
        kit_p = ep / "out/postkit.json"
        if not kit_p.exists(): sys.exit(f"buffer: {kit_p} missing — run postkit.py build first")
        kit = json.loads(kit_p.read_text())
        if kit.get("checks", {}).get("fail"): sys.exit(f"buffer: {name}: postkit has FAILs: {kit['checks']['fail']}")
        mine = [p for p in L["posts"] if p.get("episode") == name and p.get("post_id")]
        if not mine: print(f"== {name}: no posts in the ledger"); continue
        print(f"== {name}")
        only = set(a.channels.split(",")) if getattr(a, "channels", None) else None
        for prev in mine:
            platform, acc = prev["platform"], prev.get("account") or account_of(c, platform)
            if only and platform not in only: continue
            if prev.get("state") not in ("scheduled", "draft", "needs_approval"):
                print(f"   {platform:<10} {prev['post_id']} is {prev.get('state')} — cannot change (edit by hand on the network)"); continue
            row = payloads(c, ep, prev["media_url"], kit, [platform])[0]["payload"]
            row["mode"] = "customScheduled"; row["dueAt"] = prev["due_at"].replace(".000Z", "Z") if prev.get("due_at") else None
            if not row["dueAt"]: row["mode"] = c["buffer"].get("mode", "addToQueue"); row.pop("dueAt")
            if not live: print(f"   {platform:<10} DRY-RUN would replace {prev['post_id']} ({prev.get('due_at')}) · new text {len(row['text'])} chars"); continue
            cl = Client(c, acc)
            try: cur = cl.post(prev["post_id"])
            except Exception: cur = None                                    # already gone (e.g. deleted by an earlier, interrupted run)
            if cur and cur.get("status") not in ("scheduled", "draft", "needs_approval"):
                prev["state"] = cur.get("status"); save_ledger(L); print(f"   {platform:<10} now {cur.get('status')} on Buffer — left alone"); continue
            due = datetime.strptime(row["dueAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if row.get("dueAt") else None
            if due is None or due <= datetime.now(timezone.utc) + timedelta(minutes=3):   # slot already passed: next best slot for this channel
                slot = best_slot(c, platform, prev["channel_id"], taken_slots([], L))
                row["mode"] = "customScheduled"; row["dueAt"] = slot.strftime("%Y-%m-%dT%H:%M:%SZ"); print(f"   {platform:<10} slot {prev.get('due_at')} has passed → {row['dueAt']}")
            if cur: cl.delete(prev["post_id"])
            old = prev["post_id"]
            p = cl.create(row)
            prev.update({"post_id": p["id"], "state": p.get("status", "scheduled"), "due_at": p.get("dueAt"), "recopied_at": now(), "replaced": old}); save_ledger(L)
            print(f"   {platform:<10} {old} → {p['id']} at {p.get('dueAt')} ✓")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("channels"); sp.add_parser("queue")
    p = sp.add_parser("plan"); p.add_argument("episode"); p.add_argument("--media-url", required=True); p.add_argument("--channels")
    p = sp.add_parser("dispatch"); p.add_argument("episode", nargs="+"); p.add_argument("--media-url"); p.add_argument("--channels")
    p.add_argument("--live", action="store_true"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--no-verify", action="store_true", help="dry-run only: skip the media URL probe")
    p = sp.add_parser("retry"); p.add_argument("--live", action="store_true"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--channels")
    p = sp.add_parser("status"); p.add_argument("--refresh", action="store_true")
    p = sp.add_parser("recopy"); p.add_argument("episode", nargs="+"); p.add_argument("--live", action="store_true"); p.add_argument("--channels", help="comma list; default all")
    a = ap.parse_args()
    {"channels": cmd_channels, "queue": cmd_queue, "plan": cmd_plan, "dispatch": cmd_dispatch, "retry": cmd_retry, "status": cmd_status, "recopy": cmd_recopy}[a.cmd](a)


if __name__ == "__main__":
    main()
