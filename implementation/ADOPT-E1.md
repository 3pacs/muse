# ADOPT-E1 — packaged evidence manifest reconciliation

Metadata-only correction of the one defect left open at the
ADOPT-B2-R2 acceptance (docs head `e6f733c2`, PR #2), implemented on
top of the accepted B2-R2 pin `a0ee30be`. The only file changed is
`dashboard-streaming/browser-preview/BROWSER-MANIFEST.json`
(the `outputs` map). No PNG bytes changed; no App, checker, F1, or
pipeline source changed; no new browser run was performed or is
required by the brief.

## The defect

`BROWSER-MANIFEST.json` records each retained screenshot twice:
once in the top-level `outputs` map and once in its case section
(`cases[].viewports[].screenshotBytes/screenshotSha256`, plus the
`extraCaptures` entry). At the B2-R2 pin the two records disagreed
on 12 of the 19 screenshots: the `outputs` entries carried
bytes/SHA-256 values that match no packaged file, while the
per-case references matched the retained files exactly. The
reviewer's integrity proof over the packaged bytes therefore
exited 1 with 12 mismatches. All 19 PNGs themselves are
byte-identical to the accepted B2-R1/B2-R2 evidence — only the
`outputs` metadata was stale.

## The fix

Each stale `outputs` entry was recomputed from the final packaged
bytes — the retained file on disk, which is also the value the
per-case section already recorded:

| Screenshot | Was (bytes / sha256…) | Now (bytes / sha256…) |
|---|---|---|
| clustering-desktop | 112500 / cf13b428… | 112547 / 8046d6dd… |
| clustering-mobile | 74394 / 40ec09a9… | 74392 / d3693504… |
| gex-mix-desktop | 111358 / ba28d3f1… | 111372 / 837b1721… |
| gex-mix-mobile-chart | 213326 / 0d59dee6… | 213327 / 732109ca… |
| gex-mix-mobile | 78678 / d232abdc… | 78675 / 3ffc3f89… |
| last-session-desktop | 113502 / 27f53b0d… | 113486 / 1b95084e… |
| legacy-desktop | 107216 / 13811744… | 107213 / 72c04e9c… |
| legacy-mobile | 73854 / e0e502f2… | 73856 / b79e8a92… |
| signals-only-error-desktop | 106390 / 2619b321… | 106427 / 03415feb… |
| signals-only-error-mobile | 60727 / 6b660642… | 60712 / 0011383c… |
| success-desktop | 110802 / 19a75be3… | 111043 / 6d166fd6… |
| success-mobile | 78592 / fa605f62… | 78593 / cdbef630… |

The remaining 7 `outputs` PNG entries (bad-clock ×2, error ×2,
future-clock ×2, last-session-mobile) already matched and are
untouched, as are all 19 per-case/extra-capture references.

## Verification

Independent re-check of the packaged tree after the fix (every
PNG reference in the manifest — 19 `outputs` entries, 18 case
viewport references, 1 extra capture; 38 references over 19
distinct paths):

- **38/38 references match** the retained files' actual bytes and
  SHA-256; **0 cross-section conflicts** — the same path now
  carries the same (bytes, sha256) in every section.
- The same check against the pre-fix manifest reproduces the
  brief exactly: 12 mismatches, all in `outputs`, 0 in the
  per-case sections — so the corrected integrity proof exits 0.
- The two bundle outputs (`assets/app.js`, `assets/app.css`)
  remain hash-recorded only and **UNAVAILABLE** as packaged files,
  unchanged from B2-R2.
- Package `SHA256SUMS.txt` / `MANIFEST.md` regenerated for the one
  changed file plus this note; `sha256sum -c` clean.

## Provenance

Why the stale values existed: the B2-R2 browser run re-rendered
the screenshots and the `outputs` map was written from those
fresh renders, while the packaged PNGs are the retained
B2/B2-R1 captures (the standing convention — re-renders differ in
bytes on some cases). The per-case sections recorded the retained
files; the `outputs` map did not. (Spot-checked: the stale
`outputs` value for success-desktop, 110802 / 19a75be3…, is the
B2-R2 headline run's fresh render byte-for-byte; the packaged file,
111043 / 6d166fd6…, is the retained capture.) E1 aligns the map to
the packaged bytes, which are the evidence of record.
