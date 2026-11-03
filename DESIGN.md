---
version: alpha
name: TruthLens
description: Calm, trustworthy checking tool for policy analysts, students and journalists. Warm paper surfaces, one navy accent, verdict colours that always come with a label, a serif draft and a legible sans UI.
colors:
  background: "#F5F4F0"
  surface: "#FFFFFF"
  raised: "#EFEDE7"
  line: "#DCD8CE"
  line-strong: "#C9C4B8"
  ink: "#0F172A"
  ink-secondary: "#334155"
  muted: "#52606F"
  primary: "#1E3A5F"
  primary-hover: "#152C49"
  on-primary: "#FFFFFF"
  contradicted: "#B42318"
  contradicted-bg: "#FCE4DF"
  partly: "#8A4B00"
  partly-bg: "#FBEBCF"
  unverified: "#475569"
  unverified-bg: "#E6E9EE"
  supported: "#166534"
  supported-bg: "#DCEFE1"
  meter: "#16A34A"
typography:
  display:
    fontFamily: Crimson Pro, Charter, Iowan Old Style, Georgia, serif
    fontSize: 44px
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: -0.015em
  headline:
    fontFamily: Crimson Pro, Charter, Iowan Old Style, Georgia, serif
    fontSize: 26px
    fontWeight: 600
    lineHeight: 1.25
  draft:
    fontFamily: Crimson Pro, Charter, Iowan Old Style, Georgia, serif
    fontSize: 19px
    fontWeight: 400
    lineHeight: 1.75
  body:
    fontFamily: Atkinson Hyperlegible, system-ui, Segoe UI, Roboto, sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: Atkinson Hyperlegible, system-ui, Segoe UI, Roboto, sans-serif
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1
  section-label:
    fontFamily: Atkinson Hyperlegible, system-ui, Segoe UI, Roboto, sans-serif
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 0.07em
  meta:
    fontFamily: Atkinson Hyperlegible, system-ui, Segoe UI, Roboto, sans-serif
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
rounded:
  sm: 6px
  md: 10px
  lg: 12px
  card: 16px
  sheet: 18px
  full: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  page-x: 32px
  page-x-phone: 16px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    height: 44px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    borderColor: "{colors.line-strong}"
    rounded: "{rounded.md}"
    height: 44px
  card:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line}"
    rounded: "{rounded.card}"
  chip:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line-strong}"
    rounded: "{rounded.full}"
    height: 44px
  verdict-badge-contradicted:
    backgroundColor: "{colors.contradicted-bg}"
    textColor: "{colors.contradicted}"
    rounded: "{rounded.full}"
---

# TruthLens design system

This file describes how the TruthLens web app (`truthlens/webui.py`) and its static report (`truthlens/report_v2.py`) look and move. Read it before changing either, and update it when you change a token. Format: [DESIGN.md](https://github.com/google-labs-code/design.md) (tokens in the front matter, rationale below).

## Overview

TruthLens tells people whether the facts in their draft hold up. The users are policy analysts, students and journalists, most of them non-technical. The interface should feel like a careful editor's desk: calm, plain and trustworthy, with nothing that looks like a sales page or an AI demo.

- Style: Swiss minimalism with a warm paper ground (UI UX Pro Max's "Minimalism & Swiss Style" plus its "Trust & Authority" pattern), evolved from the earlier "auditor's redline" look.
- One screen, three states: **start** (drop a file, paste text or try the sample), **checking** (four honest steps), **results** (score, filter chips, highlighted draft, finding panel).
- The draft is the hero of the results. Everything else serves reading it.

## Colors

- **Paper** (`background`) behind everything; **white** (`surface`) for cards. Never a pure white page.
- **Navy** (`primary`) is the only accent: primary buttons, focus rings, links, active steps.
- **Verdict colours** come in text/background pairs, each at 4.5:1 or better: Contradicted red, Partly amber, Unverified slate, Supported green. A verdict colour is never the only signal: every highlight also has a label (badge, chip text or screen-reader text) and a distinct underline (wavy red, dotted amber, dashed slate, none for supported).
- `meter` green is used only for the score ring stroke (a graphic, 3:1 rule).
- Banned: purple/violet gradients, gradient text, neon, glassmorphism, dark-mode-by-default.

Measured contrast: muted on paper 5.9:1, muted on white 6.4:1, each verdict text on its background 5.4 to 6.2:1, white on navy 11.5:1.

## Typography

- Serif (Crimson Pro if installed, otherwise Charter / Iowan / Georgia) for the h1, result headline, the draft itself and quoted evidence: reading material.
- Sans (Atkinson Hyperlegible if installed, otherwise the system UI font) for controls, labels and explanations: interface.
- No web-font download: the app must work offline and with no CDN. Fonts are named first so they are used when present.
- Body 16px minimum; draft 19px (18px on phones) at 1.7 to 1.75 line height, measure at most 68ch. Numbers use tabular figures.

## Layout

- Max width 1240px, 32px side padding (16px on phones). Breakpoints checked at 375, 390, 768, 1024 and 1440.
- Start: single centred column (760px). Checking: one centred card (560px).
- Results: summary card on top (score ring, headline, chips, actions), then a two-column workspace: draft (fluid) and finding panel (420px, 360px under 1100px), sticky beside the draft.
- At 860px and below the panel becomes a bottom sheet (82vh max) with a scrim, a grab handle and a close button.
- No horizontal scrolling at any width; long URLs in drafts wrap (`overflow-wrap: anywhere`).

## Elevation & Depth

Flat. Cards are separated from the paper by a 1px `line` border and nothing else (no border-plus-soft-shadow "ghost cards"). The only shadow is on the phone bottom sheet, because it really sits above the page.

## Shapes

Cards 16px, buttons and inputs 10px, highlights 3px, chips and verdict badges fully rounded (small controls only). No coloured side stripes on cards, quotes or alerts: quoted evidence sits on a tinted block instead.

## Components

- **Drop zone**: a dashed 2px box with a navy icon disc; the whole box is a button (click, Enter or Space opens the file picker) so dragging is never required.
- **Tabs** (Upload a file / Paste text): ARIA tabs, arrow keys switch.
- **Steps**: four rows, pending (hollow ring), active (navy spinner, tinted row, bold), done (filled navy disc with a check). No percentages anywhere.
- **Score ring**: 128px SVG ring (88px on phones), percentage counts up once.
- **Chips**: one per verdict with a non-zero count, `aria-pressed` toggles, wrap rather than clip.
- **Highlighted sentence**: `span role=button tabindex=0` inside the paragraph so text still flows; a small coloured number follows it.
- **Finding panel**: position and prev/next buttons, verdict badge, meta line, plain-language meaning, the specific reason, Superseded notice when present, suggested fix (word diff with del/ins, Accept fix / Undo, Copy fix), "Worth knowing" warnings, evidence quotes with source-type badge, publisher, "Data as of", an "Open source (domain)" link and Copy citation, citation checks.
- **Source-type badge** (v0.3): a small outlined pill (`surface` fill, `line-strong` border, 12px bold sans) before each evidence item's publisher: data.gov.in, MoSPI, PIB, Lok Sabha, Rajya Sabha, Paper, Report, World Bank (others: Official data, Web, Cited source, Your documents). Neutral on purpose: verdict colours stay reserved for verdicts.
- **Data as of** (v0.3): one meta line under each evidence item ("Data as of 10 April 2026 (dataset updated)", "… (retrieved live; latest period 2023-24)"), in `ink-secondary`, from the evidence's `data_as_of` field. The static report shows the same text in bold in each evidence line.
- **Superseded notice** (v0.3): when a figure matches an older release or period, an amber block (`partly-bg`, warning icon, "Superseded." in bold) sits right under the reason, above the suggested fix, and is not repeated under "Worth knowing".
- **Copy citation** (v0.3): a quiet navy text button under each evidence item, next to "Open source"; copies publisher, title, source type, page, data-as-of date and URL as one plain-text line.
- **Low-confidence supports** (v0.3): a Supported verdict decided by the word-match heuristic reads "Supported · low confidence" with its own plain-language line, and the result summary says how many supported claims rest on a word match only.
- **Start screen** (v0.3): one quiet 13px muted line under the footer lists the sources checked live. The optional keys box holds the AI key and a data.gov.in key field; both are password inputs, used for one check and never stored.
- **Split headline** (v0.4.1): the results heading is the split count in words, "8 wrong · 7 supported · 3 couldn't check · 1 skipped" (plus "partly supported" when any), in the `headline` serif. The score ring is labelled "of checked" and the line under the heading says how many checked claims are supported and that "couldn't check" is not counted as wrong. UNVERIFIED reads "Couldn't check" everywhere (chips, badges, legend). The static report shows the same headline above the score, a five-figure count row (wrong, partly, supported, couldn't check, skipped) and the plain explanation of "couldn't check".
- **Source banner** (v0.4.1): an amber note (`partly-bg`, 14px body) under the summary line, only when needed: "Offline run: …" and/or "Unreachable this run: rbi (timeout, 2 claims affected); …". Static report: the same text in an amber block under the headline.
- **Failed part** (v0.4.1): for wrong and partly supported findings, a line "Failed part: 2025-26 Real GDP growth: draft 7.7%, official 7.8% (revised)" sits above the reason; the label is bold in `contradicted`. Evidence quotes are the deciding cell or sentence (about 200 characters), not the whole passage.
- **"Contains a factual claim" tag** (v0.4.1): a neutral pill (`surface` fill, `line2` border, 12px bold sans) on opinion-worded sentences whose factual core was checked, followed by "Opinion wording set aside; the factual part was checked."
- **"Unverified source" tag** (v0.4.1): an outlined pill like the source-type badge but in `partly` text and border, after the badge, for evidence from sources only tested on synthetic or rate-limited fixtures (NDAP data rows, data.gov.in, Semantic Scholar, Shodhganga); its tooltip says so.
- **Open sample report** (v0.4.1): a quiet button next to "Try the sample policy note" on the start screen, opening the bundled static report in a new tab; a muted line under it says it needs no internet.
- **Icons**: inline SVG from Lucide (ISC), 1.75 stroke, 18 to 20px. No emoji or Unicode glyphs as icons.

## Motion

Guidance from Emil Kowalski's animation standards: motion only where it explains a change, fast, interruptible, and gone under reduced motion.

- Easing: `--ease: cubic-bezier(.23,1,.32,1)` (strong ease-out) for entering; `--ease-drawer: cubic-bezier(.32,.72,0,1)` for the bottom sheet; plain `ease` for colour/hover changes. Never ease-in.
- Durations: hover and chip filter 150ms; press feedback `scale(.97)` over 160ms; state change (view enter) 240ms; finding swap 160ms; sheet 280 to 320ms; spinner 0.8s; score ring 0.9s (seen once per check, so allowed to be a little longer).
- Only `transform` and `opacity` animate (plus the SVG stroke offset of the ring). Transitions, not keyframes, for anything that can be interrupted (sheet, chips, toast).
- Keyboard navigation (J/K) does not animate or smooth-scroll.
- `prefers-reduced-motion: reduce` turns every animation and transition off; the score shows its final value at once and the active step is shown with a filled disc instead of a spinner.

## Do's and Don'ts

Do:
- Write user and evidence text with `textContent` only; innerHTML is reserved for the constant icon map.
- Keep every interactive target at least 44px high, with a visible 3px navy focus ring and `cursor: pointer`.
- Say what a verdict means in plain words before the technical reason.
- Keep copy short, sentence case, no jargon ("Worth knowing", not "Warnings").

Don't:
- Fake progress (percentages, bars that fill on a timer).
- Rely on colour alone, hover alone, or drag alone.
- Add eyebrows/kickers above headings, numbered section markers, gradient text, or decorative illustrations.
- Add a CDN, web font download or build step.
