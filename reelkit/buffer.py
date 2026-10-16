#!/usr/bin/env python3
"""Buffer dispatcher — queue a rendered episode on every enabled Buffer channel (YouTube · Instagram · Facebook).

  python3 reelkit/buffer.py channels                 # discover org + channels with the API key, write ids into config/publishing.json
  python3 reelkit/buffer.py queue                    # queue depth per channel (scheduled / daily limit)
  python3 reelkit/buffer.py plan     <ep> --media-url URL      # show the exact createPost payloads (no network)
  python3 reelkit/buffer.py dispatch <ep> --media-url URL [--live] [--channels youtube,instagram,facebook,twitter,threads]
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
UA = "TheQuizWire-reelkit/1 (+https://github.com/zainkhan122/thequizwire)"

POST_FIELDS = "id channelId status dueAt sentAt createdAt externalLink schedulingType shareMode text assets { source mimeType } error { message supportUrl }"
Q_ACCOUNT = "query { account { id email organizations { id name channelCount } } }"
Q_CHANNELS = "query($org: OrganizationId!) { channels(input: { organizationId: $org }) { id name service serviceId displayName externalLink timezone isDisconnected isLocked isQueuePaused postingSchedule { day paused times } } }"
Q_POSTS = "query($input: PostsInput!, $after: String) { posts(first: 100, after: $after, input: $input) { edges { node { " + POST_FIELDS + " } } pageInfo { hasNextPage endCursor } } }"
Q_POST = "query($input: PostInput!) { post(input: $input) { " + POST_FIELDS + " } }"
Q_LIMITS = "query($input: DailyPostingLimitsInput!) { dailyPostingLimits(input: $input) { channelId isAtLimit limit scheduled sent } }"
M_CREATE = "mutation($input: CreatePostInput!) { createPost(input: $input) { __typename ... on PostActionSuccess { post { " + POST_FIELDS + " } } ... on MutationError { message } } }"


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
                if wait > 60 or attempt + 1 == self.attempts: raise Deferred(f"rate limited; retry after {wait:.0f}s")
                time.sleep(wait + 0.5); continue
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
                if codes <= {"RATE_LIMIT_EXCEEDED"} and attempt + 1 < self.attempts: time.sleep(30); continue
                if codes & {"UNAUTHORIZED", "FORBIDDEN"}: raise BufferError(f"Buffer auth error: {msg}")
                if codes <= {"GRAPHQL_VALIDATION_FAILED", "BAD_USER_INPUT"}: raise BufferError(f"GraphQL input rejected: {msg}")
                if mutation: raise Ambiguous(f"uncertain createPost outcome ({','.join(sorted(codes))}): {msg}")
                raise Deferred(f"Buffer query failed ({','.join(sorted(codes))}): {msg}")
            if not isinstance(body.get("data"), dict):
                if mutation: raise Ambiguous("createPost returned no data — reconcile before retrying")
                raise Deferred("Buffer returned no data")
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
            base.update({"text": g["caption"], "assets": [{"video": {"url": media_url, "metadata": {"thumbnailOffset": int(g.get("thumbnailOffsetMs", 2000))}}}],
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
    present = present_accounts(c)
    if not present: sys.exit(f"buffer: none of {accounts(c)} is set")
    for acc in present:
        cl = Client(c, acc); acct = cl.account(); orgs = acct.get("organizations") or []
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
            if missing: print(f"   {platform}: channel {entry['buffer_id']} not visible through the keys present — keeping it"); continue
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
        cl = Client(c, acc); ids = [cid for _, cid in items]
        sched, complete = cl.posts(org, ids, ["scheduled", "sending"])
        lim = {l["channelId"]: l for l in cl.limits(ids)}
        for p, cid in items:
            n = sum(1 for x in sched if x["channelId"] == cid); l = lim.get(cid, {})
            print(f"   {p:<10} queued {n:>3}{'' if complete else '+'}   today: scheduled {l.get('scheduled', '?')} sent {l.get('sent', '?')} limit {l.get('limit', '—')}{'  AT LIMIT' if l.get('isAtLimit') else ''}")


def cmd_plan(a):
    c = cfg(); rows = payloads(c, a.episode, a.media_url, channels=a.channels.split(",") if a.channels else None)
    print(json.dumps(rows, indent=1, ensure_ascii=False))


def cmd_dispatch(a):
    c = cfg(); ep = Path(a.episode); name = ep.name
    if not c.get("enabled"): sys.exit("buffer: config/publishing.json enabled=false")
    kit_p = ep / "out/postkit.json"
    if not kit_p.exists(): sys.exit(f"buffer: {kit_p} missing — run reelkit/postkit.py build first")
    kit = json.loads(kit_p.read_text())
    if kit.get("checks", {}).get("fail"): sys.exit(f"buffer: postkit has FAILs: {kit['checks']['fail']}")
    want = a.channels.split(",") if a.channels else None
    rows = payloads(c, ep, a.media_url, kit, want)
    if a.no_verify and not a.live:
        print(f"media (unverified, dry-run): {a.media_url}")
    else:
        size = verify_media(a.media_url); print(f"media ok: {a.media_url} ({(size or 0) / 1e6:.1f} MB)")
    L = load_ledger(); live = a.live and not a.dry_run
    clients, existing, lim = {}, [], {}
    if live:
        ids = [r["payload"]["channelId"] for r in rows]
        if any(i.startswith("<") for i in ids): sys.exit("buffer: channel ids missing — run `buffer.py channels`")
        for (acc, org), items in groups(c, [r["platform"] for r in rows]).items():
            cl = clients[acc] = clients.get(acc) or Client(c, acc); gids = [cid for _, cid in items]
            win = int(c["buffer"].get("dedupe_window_days", 14))                   # a lost createPost response is minutes old, not months
            ex, complete = cl.posts(org, gids, ["scheduled", "sending", "sent", "needs_approval", "draft"], max_pages=10, since_days=win)
            if not complete: sys.exit(f"buffer: post scan incomplete (> 1000 posts in {win} days) — refusing to risk a duplicate; lower buffer.dedupe_window_days")
            existing += ex; lim.update({l["channelId"]: l for l in cl.limits(gids)})
    created, skipped, failed = 0, 0, 0
    for r in rows:
        platform, payload = r["platform"], r["payload"]
        prev = ledger_entry(L, name, platform)
        if prev:
            print(f"   {platform:<10} already queued as {prev['post_id']} ({prev['state']}) — skip"); skipped += 1; continue
        acc = account_of(c, platform)
        if not live:
            print(f"   {platform:<10} DRY-RUN would create addToQueue post · text {len(payload['text'])} chars · channel {payload['channelId']} · via {acc or 'account unknown'}"); continue
        if acc not in clients:
            print(f"   {platform:<10} deferred: {'channel account unknown' if not acc else acc + ' secret not set'} — nothing sent"); continue
        same = [p for p in existing if p["channelId"] == payload["channelId"] and any(x.get("source") == a.media_url for x in p.get("assets") or [])]
        if same:                                                                       # a lost response from an earlier run: adopt it
            p = same[0]; print(f"   {platform:<10} found existing post {p['id']} ({p['status']}) with this media — adopting")
            L["posts"].append({"episode": name, "platform": platform, "post_id": p["id"], "channel_id": payload["channelId"], "state": p["status"],
                               "media_url": a.media_url, "due_at": p.get("dueAt"), "created_at": p.get("createdAt"), "recorded_at": now(), "adopted": True, "account": acc})
            save_ledger(L); skipped += 1; continue
        queued = sum(1 for p in existing if p["channelId"] == payload["channelId"] and p["status"] in ("scheduled", "sending"))
        cap = int(c["buffer"].get("queue_limit_per_channel", 14))
        if queued >= cap:
            print(f"   {platform:<10} queue has {queued} posts (cap {cap}) — deferring this episode"); continue
        if lim.get(payload["channelId"], {}).get("isAtLimit"):
            print(f"   {platform:<10} Buffer daily posting limit reached — deferring"); continue
        try:
            p = clients[acc].create(payload)
        except Ambiguous as e:
            L["posts"].append({"episode": name, "platform": platform, "post_id": None, "channel_id": payload["channelId"], "state": "ambiguous",
                               "media_url": a.media_url, "recorded_at": now(), "error": str(e)}); save_ledger(L)
            sys.exit(f"buffer: {platform}: {e} — ledger marked ambiguous; rerun reconciles before creating again")
        except Deferred as e:
            print(f"   {platform:<10} deferred: {e}"); continue
        except Rejected as e:                                                          # nothing created; other channels go on; job exits 1
            print(f"   {platform:<10} REJECTED: {e}")
            L["posts"].append({"episode": name, "platform": platform, "post_id": None, "channel_id": payload["channelId"], "state": "error",
                               "media_url": a.media_url, "recorded_at": now(), "error": str(e)[:300], "account": acc}); save_ledger(L); failed += 1; continue
        L["posts"].append({"episode": name, "platform": platform, "post_id": p["id"], "channel_id": payload["channelId"], "state": p["status"],
                           "media_url": a.media_url, "due_at": p.get("dueAt"), "created_at": p.get("createdAt"), "recorded_at": now(),
                           "title": kit["youtube"]["title"] if platform == "youtube" else None, "account": acc})
        save_ledger(L); created += 1
        print(f"   {platform:<10} queued → post {p['id']} · status {p['status']} · due {p.get('dueAt') or 'next free slot'}")
    print(f"buffer: {name} · {'LIVE' if live else 'dry-run'} · created {created} · skipped {skipped} · rejected {failed}")
    if failed: sys.exit(1)


def cmd_status(a):
    c = cfg(); L = load_ledger()
    if a.refresh:
        clients = {}
        for p in L["posts"]:
            if p.get("post_id") and p.get("state") not in ("sent",):
                acc = p.get("account") or account_of(c, p["platform"])
                if not token(acc, required=False): p["refresh_error"] = f"{acc} not set"; continue
                cl = clients[acc] = clients.get(acc) or Client(c, acc)
                try:
                    q = cl.post(p["post_id"]); p.update({"state": q["status"], "due_at": q.get("dueAt"), "sent_at": q.get("sentAt"), "external_link": q.get("externalLink"), "refreshed_at": now()})
                    if q.get("error"): p["error"] = q["error"].get("message")
                except BufferError as e:
                    p["refresh_error"] = str(e)
        save_ledger(L)
    for p in L["posts"]:
        print(f"   {p['episode']:<44} {p['platform']:<10} {str(p.get('state')):<12} {p.get('post_id') or '—':<26} due {p.get('due_at') or '—'}  {p.get('external_link') or ''}")
    print(f"ledger: {len(L['posts'])} record(s)")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("channels"); sp.add_parser("queue")
    p = sp.add_parser("plan"); p.add_argument("episode"); p.add_argument("--media-url", required=True); p.add_argument("--channels")
    p = sp.add_parser("dispatch"); p.add_argument("episode"); p.add_argument("--media-url", required=True); p.add_argument("--channels")
    p.add_argument("--live", action="store_true"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--no-verify", action="store_true", help="dry-run only: skip the media URL probe")
    p = sp.add_parser("status"); p.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    {"channels": cmd_channels, "queue": cmd_queue, "plan": cmd_plan, "dispatch": cmd_dispatch, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
