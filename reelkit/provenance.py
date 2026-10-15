#!/usr/bin/env python3
"""Provenance gate: every file that ends up in the video has a known origin and a licence we may use.

  python3 reelkit/provenance.py <ep> [--hf <hf_dir>] [--report out/provenance.json] [--credits-md out/credits.md]

Sources of truth
  <ep>/media.json  files{path: {sha256, size, kind, licence, provider, source, credit, ai, realistic, prompt|spec,
                   derived_from, op, screen_credit, legacy}}  +  generated{name: {...}} for build-time assets
  fonts/LICENSES.md + the licence embedded in each font; the GSAP header for engine JS
FAIL
  - a media file without kind / licence / provider / source, or with a licence outside the allow-list
    (share-alike, non-commercial, no-derivatives, unknown and fair-use are refused for monetised video)
  - photo/archive/CC-BY without a credit; photo/archive without an http(s) source
  - AI media without a prompt or spec (unless marked legacy → WARN), or without ai/realistic flags
  - derived_from pointing at nothing; a clip spec (clips.json#id) that doesn't exist
  - built file (hf/assets, hf/fonts, *.js) with no provenance → nothing ships without an origin
  - photo/archive whose screen_credit is not visible in the composition
  - POST_KIT.md missing a credited author, or missing the AI disclosure while AI media is used
WARN
  - legacy AI media (prompt not recorded), a generated clip whose clips.json prompt changed since generation,
    a clip not registered in the clip cache or whose cache_key no longer matches its clips.json spec (drift)
Writes a paste-ready credits block (--credits-md).
"""
import argparse, hashlib, html, json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALLOWED = {
    "PD": "public domain", "PD-USGov": "U.S. Government work, public domain", "CC0-1.0": "CC0",
    "CC-BY-4.0": "CC BY 4.0 (attribution)", "CC-BY-3.0": "CC BY 3.0 (attribution)",
    "own": "original work (procedural / hand-made for this project)",
    "own-ai": "AI-generated for this project (tool terms permit commercial use)",
    "own-tts": "AI voice generated for this project",
    "OFL-1.1": "SIL Open Font License 1.1", "Apache-2.0": "Apache 2.0", "GSAP-Standard": "GSAP Standard 'No Charge' licence",
    "ISC": "ISC licence (code / data: d3, topojson, world-atlas)", "MIT": "MIT licence (code)", "BSD-3-Clause": "BSD 3-clause (code)",
    # geodata: the produced work (a video frame) only needs attribution; ODbL share-alike applies to derivative DATABASES, which we never publish
    "ODbL-1.0": "Open Database License 1.0 (OpenStreetMap — attribution '© OpenStreetMap contributors' required)",
    "Copernicus": "Copernicus Sentinel data licence (attribution 'Contains modified Copernicus Sentinel data' required)",
}
ATTRIBUTION = {"CC-BY-4.0", "CC-BY-3.0", "ODbL-1.0", "Copernicus"}
REFUSED = re.compile(r"(?<![A-Za-z])SA(?![A-Za-z])|NC|ND|unknown|fair.?use|all.rights", re.I)
KINDS = {"plate", "clip", "archive", "photo", "vo", "music", "sfx", "texture", "font", "code", "mix", "data", "image"}   # image = generated graphics (basemap rasters, flag/sticker SVGs)
# vendored runtime JS shipped inside every composition (engine/vendor/LICENSES.md is the human-readable table)
VENDOR_JS = {"gsap.min.js": "GSAP-Standard", "d3-geo.min.js": "ISC", "d3-array.min.js": "ISC", "topojson-client.min.js": "ISC", "geo-runtime.js": "own"}
NEEDS_CREDIT = {"photo", "archive"}


def norm(s):
    return re.sub(r"\s+", " ", html.unescape(s)).strip().lower()


def font_licences():
    """file → licence id from fonts/LICENSES.md, cross-checked with the licence embedded in the font."""
    table, out = {}, {}
    lic = REPO / "fonts" / "LICENSES.md"
    if lic.exists():
        for row in lic.read_text().splitlines():
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) == 3 and cells[0].lower().endswith(".ttf"):
                for f in re.split(r",\s*", cells[0]):
                    table[f] = "OFL-1.1" if "OFL" in cells[2] else "Apache-2.0" if "Apache" in cells[2] else cells[2]
    for f, lid in table.items():
        out[f] = {"licence": lid, "embedded": None}
        p = REPO / "fonts" / f
        try:
            from fontTools.ttLib import TTFont
            desc = (TTFont(str(p))["name"].getDebugName(13) or "")
            out[f]["embedded"] = "OFL-1.1" if "Open Font License" in desc else "Apache-2.0" if "Apache" in desc else desc[:60]
        except Exception:
            pass                                                     # fontTools absent (CI): table only
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ep"); ap.add_argument("--hf"); ap.add_argument("--report"); ap.add_argument("--credits-md")
    a = ap.parse_args()
    ep = Path(a.ep).resolve()
    man = json.loads((ep / "media.json").read_text())
    files, gen = man.get("files", {}), man.get("generated", {})
    clips = {c["id"]: c for c in json.loads((ep / "clips.json").read_text())["clips"]} if (ep / "clips.json").exists() else {}
    F, W = [], []

    def check_entry(name, e, built=False):
        lic = e.get("licence", "")
        for k in ("kind", "licence", "provider", "source"):
            if not e.get(k):
                F.append(f"{name}: missing {k}")
        if e.get("kind") and e["kind"] not in KINDS:
            F.append(f"{name}: kind '{e['kind']}' not in {sorted(KINDS)}")
        if lic and lic not in ALLOWED:
            F.append(f"{name}: licence '{lic}' not allowed" + (" (share-alike/NC/ND/unknown refused)" if REFUSED.search(lic) else f" — use one of {sorted(ALLOWED)}"))
        if (e.get("kind") in NEEDS_CREDIT or lic in ATTRIBUTION) and not e.get("credit"):
            F.append(f"{name}: needs a credit line")
        if e.get("kind") in NEEDS_CREDIT and not str(e.get("source", "")).startswith("http"):
            F.append(f"{name}: {e['kind']} needs an http(s) source URL")
        if e.get("kind") in ("plate", "clip", "vo") and "ai" not in e:
            F.append(f"{name}: say whether it is AI-made (ai: true/false)")
        if e.get("ai"):
            if "realistic" not in e:
                F.append(f"{name}: AI media needs realistic: true/false (platform disclosure)")
            if not (e.get("prompt") or e.get("spec")):
                (W if e.get("legacy") else F).append(f"{name}: AI media without prompt/spec" + (f" (legacy: {e['legacy']})" if e.get("legacy") else ""))
        spec = str(e.get("spec", ""))
        if spec.startswith("clips.json#"):
            cid = spec.split("#", 1)[1]
            c = clips.get(cid)
            if not c:
                F.append(f"{name}: spec {spec} not in clips.json")
            elif e.get("prompt_sha1") and c.get("prompt") and hashlib.sha1(c["prompt"].encode()).hexdigest() != e["prompt_sha1"]:
                W.append(f"{name}: clips.json prompt for {cid} changed after generation (file no longer matches its spec)")
            elif c.get("engine") == "url" and c.get("source") and e.get("source") != c["source"]:
                F.append(f"{name}: source differs from clips.json ({c['source']})")
            if c and name.startswith("clips/"):          # clip cache: the file must be the output of today's spec
                sys.path.insert(0, str(Path(__file__).resolve().parent)); import clips as _clips, clipcache as _cc
                try:
                    k = _cc.make_key(_clips.call_spec(c, ep))
                    if not e.get("cache_key"): W.append(f"{name}: not registered in the clip cache (clips.py adopt)")
                    elif e["cache_key"] != k: W.append(f"{name}: cache_key drift — clips.json/plate changed since this clip was made (regenerate or revert)")
                except (ValueError, FileNotFoundError) as x:
                    W.append(f"{name}: cache key not computable ({x})")
        d = e.get("derived_from")
        if d and not (d in files or str(d).startswith("http") or d.startswith("procedural")):
            F.append(f"{name}: derived_from {d} not found")

    for k, e in files.items():
        check_entry(k, e)
    for k, e in gen.items():
        e2 = {"source": e.get("by") or e.get("derived_from"), "provider": e.get("by", "build"), **e}
        check_entry(f"generated:{k}", e2)

    # ---------- built output audit ----------
    hf = Path(a.hf) if a.hf else Path.home() / ".cache/build" / ep.name / "hf"
    fonts = font_licences()
    audit = []
    if (hf / "index.html").exists():
        text = norm(re.sub(r"<[^>]+>", " ", (hf / "index.html").read_text()))
        for p in sorted(hf.rglob("*")):
            if p.is_dir() or "__pycache__" in p.parts or any(x.startswith(".") for x in p.relative_to(hf).parts) or p.name in ("index.html", "meta.json", "hyperframes.json", "package.json"):
                continue
            rel = p.relative_to(hf).as_posix()
            src = None
            if rel.startswith("assets/"):
                name = rel[len("assets/"):]
                for cand in (f"assets/{name}", name if name.startswith("clips/") else None):
                    if cand and cand in files:
                        src = cand
                if not src and (name in gen or Path(name).name in gen):
                    src = f"generated:{name if name in gen else Path(name).name}"
            elif rel.startswith("fonts/"):
                fl = fonts.get(p.name)
                if fl:
                    src = f"font:{fl['licence']}"
                    if fl["embedded"] and fl["embedded"] != fl["licence"]:
                        F.append(f"{rel}: LICENSES.md says {fl['licence']} but the font embeds '{fl['embedded']}'")
            elif rel.endswith(".js"):
                head = p.read_text(errors="ignore")[:600]
                if "gsap.com/standard-license" in head:
                    src = "GSAP-Standard"
                elif p.name in VENDOR_JS and (VENDOR_JS[p.name] == "own" or "Copyright" in head or "License" in head):
                    src = f"vendor:{VENDOR_JS[p.name]}"
            audit.append({"file": rel, "provenance": src})
            if not src:
                F.append(f"built file {rel} has no provenance (add it to media.json 'files' or 'generated')")
        for k, e in files.items():
            if e.get("kind") in NEEDS_CREDIT:
                sc = e.get("screen_credit")
                if not sc:
                    F.append(f"{k}: {e['kind']} needs screen_credit (the on-screen credit text)")
                elif norm(sc) not in text:
                    F.append(f"{k}: on-screen credit not found in composition: “{sc}”")
    else:
        W.append(f"{hf}/index.html not built — output audit and on-screen credits not checked")

    # ---------- post kit: credits + AI disclosure ----------
    pk = ep / "POST_KIT.md"
    pkt = norm(pk.read_text()) if pk.exists() else ""
    for k, e in files.items():
        if e.get("kind") in NEEDS_CREDIT or e.get("licence") in ATTRIBUTION:
            for author in e.get("credit_authors", []):
                if norm(author) not in pkt:
                    F.append(f"POST_KIT.md does not credit {author} ({k})")
    ai = [k for k, e in files.items() if e.get("ai")]
    if ai and not re.search(r"ai disclosure|ai-generated|altered or synthetic", pkt):
        F.append(f"{len(ai)} AI media files but POST_KIT.md has no AI disclosure")
    realistic = [k for k in ai if files[k].get("realistic")]

    # ---------- credits block ----------
    if a.credits_md:
        L = ["Credits & disclosures:"]
        for k, e in sorted(files.items(), key=lambda kv: (kv[1].get("kind") not in NEEDS_CREDIT, kv[0])):
            if e.get("credit"):
                L.append(f"• {e['credit']} — {ALLOWED.get(e.get('licence'), e.get('licence'))}. {e.get('source', '')}")
        kinds = sorted({files[k]['kind'] for k in ai})
        if ai:
            L.append(f"• AI-generated {', '.join(kinds)} ({len(ai)} files). " +
                     ("Includes realistic synthetic media: disclose as altered/synthetic content." if realistic else
                      "Stylised illustration and voice, not realistic footage of real people."))
        L.append("• Fonts: Oswald, Anton, DM Serif Display (SIL OFL 1.1); Special Elite (Apache 2.0). Music and sound design: original, procedurally generated.")
        Path(a.credits_md).parent.mkdir(parents=True, exist_ok=True)
        Path(a.credits_md).write_text("\n".join(L) + "\n")

    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps({"fails": F, "warns": W, "built": audit, "ai_files": ai, "realistic_ai": realistic}, ensure_ascii=False, indent=1))
    for x in F:
        print("  FAIL ", x)
    for x in W:
        print("  WARN ", x)
    print(f"provenance: {len(files)} media + {len(gen)} generated · {len(audit)} built files audited · AI {len(ai)} "
          f"(realistic {len(realistic)}) · FAIL {len(F)} · WARN {len(W)}")
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
