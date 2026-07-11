# QuantLab — Demo Freeze Checklist (Phase 42.0)

A "demo freeze" pins the exact state of the repo before recording the demo
video, capturing final screenshots, and posting publicly — so what you show
is what the repo actually contains. Fill in the placeholders by hand; nothing
in this repo automates any of it.

## 1. Freeze record

| Field | Value |
|---|---|
| Freeze date | `____-__-__` (fill in) |
| Frozen commit hash | `_______` (`git log -1 --format=%h`) |
| Tag at freeze | `v4.__._-________-v1` (created manually after review) |
| Backend test count at freeze | `____ passed` (from a real run — see runbook §9) |
| Typecheck at freeze | exit `_` (from a real run) |
| `npm run build` at freeze | user-run: `______` (record the real outcome) |

## 2. Demo route order (frozen)

Present in exactly this order — it matches
[`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md):

1. Portfolio Showcase
2. Demo Center
3. Scenario Studio
4. Research Workspace
5. Data Reliability Center
6. QA Command Center
7. Release Notes Center

## 3. Screenshot list

- [ ] All captures in [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md)
      taken **at the frozen commit** (retake any that predate the freeze).
- [ ] Filenames include the page name; captions match what is on screen.
- [ ] No screenshot shows an error state, `NaN`, or dev-tools clutter.

## 4. Video demo list

- [ ] One rehearsal run of the chosen script length (90 s / 3 min / 7 min)
      completed without an unplanned page.
- [ ] Recording resolution and window size chosen (hide bookmarks/tabs).
- [ ] Script open on a second screen; timings from
      [`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md) /
      [`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md).
- [ ] Recorded at the frozen commit; re-record if anything changes.

## 5. LinkedIn copy list

- [ ] Draft chosen from [`LINKEDIN_POST_DRAFTS.md`](LINKEDIN_POST_DRAFTS.md).
- [ ] Claims cross-checked against
      [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) — nothing
      the limitations doc contradicts.
- [ ] Repo link and (optional) video link verified after posting privately
      first.

## 6. README final check

- [ ] Renders cleanly on GitHub (headings, code blocks, tables).
- [ ] Every "Project docs" link resolves.
- [ ] Ground-rules blockquote intact; test counts match the latest real run.

## 7. Docs final check

- [ ] The six Phase 42 docs cross-link correctly.
- [ ] `docs/ROADMAP.md` has the current phase entry;
      `docs/LIMITATIONS.md` ledger is current.
- [ ] `VERSION`, `docs/VERSION_MANIFEST.md`, and the Release Notes Center
      page agree on the version label.

## 8. Known limitations final check

- [ ] [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) read once,
      top to bottom, against the actual product — nothing stale, nothing
      missing that a viewer would notice in the demo.

## 9. Do-not-change list (from freeze until the demo is published)

- **No new features.**
- **No styling rewrites** (theme tokens, layout, component styles).
- **No dependency upgrades** (`package.json`, `requirements.txt`).
- **No route renames** (View ids, sidebar labels, palette entries).
- **No external provider changes** (flags, defaults, fallbacks).
- **No CI workflow changes** (`.github/workflows/ci.yml`).
- **No generated cache commits** (`.next\`, `artifacts\`, `__pycache__`,
  `node_modules` — see [`REPOSITORY_HYGIENE.md`](REPOSITORY_HYGIENE.md)).

## 10. Allowed last-minute fixes (and nothing else)

- Typo fix (docs or UI copy).
- Broken link fix.
- Safety wording fix (removing an overclaim always qualifies).
- Screenshot caption fix.
- Route label fix (label text only — never the route id).

Anything bigger breaks the freeze: make the change, then re-run the smoke
pass in [`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md) and
restart this checklist with a new freeze record.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; not investment
advice; not production trading, risk, or compliance infrastructure. A freeze
is a discipline for honest demos — not a release certification.
