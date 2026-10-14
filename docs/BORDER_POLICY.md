# BORDER_POLICY.md — how QuizWire draws and narrates contested ground

Owner rule (2026-10-14): *sensitive borders are included, and every one is labelled with who holds/controls it and who claims it.*
This file is the human policy; `docs/border_registry.json` is the machine copy that `reelkit/geolint.py` enforces (P4).
Editing either one is a policy change: cite the source, bump `as_of`, update both.

## The five rules
1. **Show, don't hide.** A map that touches a registry region (named in the script, on screen, or inside a zoomed bbox narrower
   than 40°) must draw the disputed polygon(s) (Natural Earth 10m `admin_0_disputed_areas`) with the dashed `disputed` style and
   a policy plate per polygon. Omitting the region to avoid the topic is a gate failure, not a neutral choice.
2. **Administers / claims — never owns.** Plates and narration use *Administered by X* and *Claimed by Y*. Banned words on
   disputed ground: owns, belongs to, is part of, rightful, occupied (as a label), "Pakistan-occupied", "Indian-occupied",
   PoK/IoK. `research.json.guardrails` carries these as regexes and `factcheck.py` fails the episode on a hit (VO, screen, POST_KIT).
3. **Dated.** Every `disputed` entry has `as_of: YYYY-MM` and a `source`. Control can change (Nagorno-Karabakh 2023, Hans Island
   2022). An entry older than 12 months at render time is a geolint warning; re-verify and bump it.
4. **One frame, all sides.** If one claimant's name is on screen, the other's is too, in the same plate, same type size. The
   controller's name comes first only because it answers "who holds it today", never as endorsement.
5. **Contested names: both or neither.** Senkaku / Diaoyu, Dokdo / Takeshima, Falklands / Malvinas, "the Gulf" (not Persian/Arabian
   alone), Sea of Japan / East Sea. Capitals and city names follow the administering authority's spelling.

## What geolint checks (P4)
- `geo.json` scene `disputed[]` has an entry for every registry `ne_name` that intersects the scene (mentioned anywhere in the
  episode text or inside the zoomed bbox) with `controller`, `claimants[]`, `as_of`, `source`, `label_at` (lon/lat inside the stage).
- `engine/compose.py` turns each entry into a policy plate (`engine/geo.py policy_label_html`): **Name** / Administered by … /
  Claimed by …, and a dashed outline layer; `factcheck.py` reads those plates from the inline scene spec, so every plate string must
  also be anchored by a claim in `research.json` (that is how the ledger forces the sourcing).
- Taiwan, Kosovo, Somaliland, Northern Cyprus, Transnistria, Abkhazia/South Ossetia: drawn as their own outline with the controller
  named as the governing authority and the claimant(s) listed; no "country of" wording either way.
- Maritime claims (South China Sea, Sir Creek, Essequibo sea area) are lines/areas with the same plate, sourced to the tribunal or
  treaty text listed in the registry.

## Script wording that passes
- "K2 rises in Gilgit-Baltistan, administered by Pakistan and claimed by India, part of the wider Kashmir dispute."
- "Crimea has been under Russian control since 2014; Ukraine and most UN members regard it as Ukrainian territory."
- "Taiwan is self-governing; the People's Republic of China claims it."

## Script wording that fails
- "K2 is in Pakistan." (sovereignty asserted on contested ground — write *Pakistan-administered Gilgit-Baltistan*)
- "Indian Kashmir" / "Pakistani Kashmir" as bare labels (use *Indian-administered* / *Pakistan-administered*)
- Any map that colours a disputed area in a claimant's national fill without the dashed outline and plate.

## Registry (generated from docs/border_registry.json — do not edit by hand)
| id | region | parts: controller · claimants | as_of |
|---|---|---|---|
| `kashmir` | Kashmir | Jammu and Kashmir: **India** administers · claimed by Pakistan; Azad Kashmir: **Pakistan** administers · claimed by India; Gilgit-Baltistan: **Pakistan** administers · claimed by India; Aksai Chin: **China** administers · claimed by India; Shaksam Valley: **China** administers · claimed by India; Siachen Glacier: **India** administers · claimed by Pakistan; Demchok: **India** administers · claimed by China | 2026-10 |
| `arunachal` | Arunachal Pradesh | Arunachal Pradesh: **India** administers · claimed by China | 2026-10 |
| `taiwan` | Taiwan | Taiwan: **Republic of China (Taiwan) government** administers · claimed by People's Republic of China | 2026-10 |
| `crimea` | Crimea | Crimea: **Russia (occupied since 2014)** administers · claimed by Ukraine (internationally recognised sovereign) | 2026-10 |
| `donbas` | Donbas | Donetsk People's Republic: **Russia (partially occupied; active front line)** administers · claimed by Ukraine (internationally recognised sovereign); Luhansk People's Republic: **Russia (occupied; active front line)** administers · claimed by Ukraine (internationally recognised sovereign) | 2026-10 |
| `golan` | Golan Heights | Golan Heights: **Israel (occupied since 1967)** administers · claimed by Syria | 2026-10 |
| `palestine` | Palestinian territories | West Bank: **Israel (occupation; Palestinian Authority in Areas A/B)** administers · claimed by State of Palestine; Gaza: **contested (Israel controls access; situation changes — date every use)** administers · claimed by State of Palestine | 2026-10 |
| `western_sahara` | Western Sahara | W. Sahara: **Morocco (≈80 %, west of the berm); Polisario/SADR east of the berm** administers · claimed by Sahrawi Arab Democratic Republic, Morocco | 2026-10 |
| `kosovo` | Kosovo | Kosovo: **Republic of Kosovo (self-governing since 2008)** administers · claimed by Serbia | 2026-10 |
| `north_cyprus` | Northern Cyprus | N. Cyprus: **Turkish Cypriot administration (recognised only by Türkiye)** administers · claimed by Republic of Cyprus | 2026-10 |
| `abkhazia_ossetia` | Abkhazia and South Ossetia | Abkhazia: **self-administered, Russian-backed** administers · claimed by Georgia (internationally recognised sovereign); South Ossetia: **self-administered, Russian-backed** administers · claimed by Georgia (internationally recognised sovereign) | 2026-10 |
| `transnistria` | Transnistria | Transnistria: **self-administered** administers · claimed by Moldova (internationally recognised sovereign) | 2026-10 |
| `karabakh` | Nagorno-Karabakh | Artsakh: **Azerbaijan (since September 2023)** administers · claimed by — | 2026-10 |
| `somaliland` | Somaliland | Somaliland: **Republic of Somaliland (self-governing since 1991, unrecognised)** administers · claimed by Somalia | 2026-10 |
| `falklands` | Falkland Islands | Falkland Islands: **United Kingdom (British Overseas Territory)** administers · claimed by Argentina | 2026-10 |
| `gibraltar` | Gibraltar | Gibraltar: **United Kingdom** administers · claimed by Spain | 2026-10 |
| `ceuta_melilla` | Ceuta and Melilla | Ceuta: **Spain** administers · claimed by Morocco; Melilla: **Spain** administers · claimed by Morocco | 2026-10 |
| `kuril` | Kuril Islands | Kuril Islands: **Russia (since 1945)** administers · claimed by Japan (southern four islands) | 2026-10 |
| `senkaku` | Senkaku / Diaoyu Islands | Senkaku / Diaoyu Islands: **Japan** administers · claimed by People's Republic of China, Taiwan | 2026-10 |
| `dokdo` | Dokdo / Takeshima | Dokdo / Takeshima: **South Korea** administers · claimed by Japan | 2026-10 |
| `south_china_sea` | South China Sea islands | South China Sea islands: **features held variously by China, Vietnam, the Philippines, Malaysia, Taiwan** administers · claimed by China, Vietnam, Philippines, Malaysia, Brunei, Taiwan | 2026-10 |
| `essequibo` | Essequibo | West of Essequibo River: **Guyana** administers · claimed by Venezuela | 2026-10 |
| `halaib_bir_tawil` | Halaib Triangle and Bir Tawil | Halaib Triangle: **Egypt** administers · claimed by Sudan; Bir Tawil: **claimed by neither Egypt nor Sudan (terra nullius)** administers · claimed by — | 2026-10 |
| `abyei` | Abyei | Abyei: **joint/contested (UNISFA-patrolled)** administers · claimed by Sudan, South Sudan | 2026-10 |
| `ilemi` | Ilemi Triangle | Ilemi Triangle: **Kenya** administers · claimed by South Sudan | 2026-10 |
| `chagos` | Chagos Archipelago | Chagos Archipelago: **United Kingdom (2024 agreement to transfer sovereignty to Mauritius; verify status before use)** administers · claimed by Mauritius | 2026-10 |
| `sir_creek` | Sir Creek | Sir Creek: **boundary undemarcated in the creek** administers · claimed by India, Pakistan | 2026-10 |
| `doklam` | Doklam | Doklam: **Bhutan (contested by China)** administers · claimed by China | 2026-10 |
| `hans_island` | Hans Island | Hans Island: **divided between Canada and Denmark (Greenland) by the 2022 agreement** administers · claimed by — | 2026-10 |

Sources are in the JSON per region (Natural Earth v5 disputed areas, CIA World Factbook disputes, UN GA 68/262, UNSC 497, PCA case 7,
ICJ, MOFA Japan, 2022 Canada–Denmark agreement). `python3 reelkit/geodata.py disputed <name>` lists what Natural Earth ships.
