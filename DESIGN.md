---
name: SIGNFORGE
description: Low-resource sign-language corpus builder. The model helps decide what data to collect next.
colors:
  navy: "#14163a"
  indigo: "#3b3f9e"
  lavender: "#c9c6f2"
  teal: "#115e59"
  background: "#f7f7fc"
  surface: "#ffffff"
  warning-tint: "#fef3c7"
  demo-badge: "#fde68a"
  error-tint: "#fef2f2"
  skeleton-body: "#c9c6f2"
  skeleton-left-hand: "#5eead4"
  skeleton-right-hand: "#fcd34d"
typography:
  display:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(1.875rem, 4vw, 2.25rem)"
    fontWeight: 700
    lineHeight: 1.25
  headline:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
rounded:
  md: "6px"
  lg: "8px"
  xl: "12px"
  2xl: "16px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xl}"
    padding: "16px"
  button-primary:
    backgroundColor: "{colors.indigo}"
    textColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  button-record:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  button-secondary:
    textColor: "{colors.indigo}"
    rounded: "{rounded.lg}"
    padding: "8px 12px"
  badge-demo:
    backgroundColor: "{colors.demo-badge}"
    textColor: "{colors.navy}"
    rounded: "{rounded.md}"
    padding: "2px 8px"
  hero:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.surface}"
    rounded: "{rounded.2xl}"
    padding: "32px"
---

# Design System: SIGNFORGE

## Overview

**Creative North Star: "The Calibrated Workbench"** (our call, drawn from CLAUDE.md §4.1)

SIGNFORGE is a research and data-operations tool, not a consumer translator. It should feel like a precise, humane lab instrument: calm surfaces, dense but readable tables, and every number traceable to a real source. The deck's navy, indigo and lavender carry the identity; teal marks collection and progress; amber marks anything waiting or synthetic; red is only for errors and rejections.

Honesty is a visual rule here. Missing results say "Not evaluated yet", never 0%. Synthetic data always wears the DEMO DATA badge. Automated QC and human linguistic review never share a badge or a colour.

**Key Characteristics:**
- Light workbench surfaces (off-white page, white cards), with one deep navy hero.
- System font stack: no web-font download, fast on venue Wi-Fi.
- Status always says its state in words, never colour alone.
- The skeleton replay is the product's signature image: landmarks only, never video.

## Colors

A cool, deep palette with one warm signal colour.

- **Navy `#14163a`:** text, sidebar, hero base.
- **Indigo `#3b3f9e`:** primary actions, links, active nav, and the hero gradient's end.
- **Lavender `#c9c6f2`:** borders, quiet tints, text on navy, the skeleton's body.
- **Teal `#115e59`:** "record", "built", "approved" and "succeeded". It's darkened to teal-800 so teal text on its own 15% tint stays above 4.5:1.
- **Amber (Tailwind amber-100/200/800/950):** pending review, warnings, blocked, and the DEMO DATA badge.
- **Red (Tailwind red-50/100/700/900):** errors, rejection and failed QC only.
- **Skeleton:** lavender for the body, teal-300 `#5eead4` for the signer's left hand, amber-300 `#fcd34d` for the right. These are canvas-only colours and are always the same, so viewers learn which hand is which.

## Typography

- **Font:** the system stack throughout.
- **Display:** the hero headline only, bold, 30–36px.
- **Headline:** page H1s at 24px bold.
- **Title:** card headings at 16px semibold.
- **Body:** 14px, capped at 58ch (about 75 characters) per line, with `text-wrap: pretty` against one-word last lines.
- **Label:** 12px, for metadata and captions.
- **Numbers:** tables and metric values use tabular numerals, so columns align.

## Layout

- **Desktop:** a left sidebar (224px) and a main column capped at 1152px.
- **Below `md`:** the sidebar becomes a top bar, and the nav scrolls horizontally.
- **Spacing:** an 8px rhythm, with 24px between page sections.
- **Wide tables:** they scroll inside their own card, and the page never scrolls sideways.
- **Touch screens (`pointer: coarse`):** every control in `main` is at least 44px tall.

## Elevation & Depth

Flat. Depth comes from tonal layering (page → white card → tinted inset) and 1px lavender borders, not shadows. The hero is the only full-bleed colour block.

## Shapes

- 6px for badges.
- 8px for buttons, inputs and chips.
- 12px for cards.
- 16px for the hero.
- No left- or right-edge accent stripes, and no nested cards.

## Components

- **Card:** `card` in `frontend/components/ui.tsx`. White, 1px lavender border, 12px radius, 16px padding. Capture sections add `space-y-3`.
- **DemoBadge:** `DemoBadge` in `frontend/components/ui.tsx`. The only DEMO DATA marker; don't hand-roll another.
- **Buttons:**
  - Indigo is the primary action.
  - Teal is for record or approve.
  - The outlined-indigo variant is secondary.
  - Outlined amber is for DEMO actions.
  - Red is for reject.
  - Disabled buttons drop to 60% opacity (still legible).
- **Status chips:** a tint background plus text, with the state also written for screen readers. The loop chips use authored 16px SVG icons (check, alert, ring), not glyphs.
- **Skeleton replay:** `LandmarkReplay` and `lib/skeleton.ts`.
  - It draws upper body and hands only, fitted to the signer.
  - The display is smoothed; stored data never is.
  - It shows a single still frame under reduced motion and pauses when off-screen.

## Do's and Don'ts

**Terminology (use these words, one meaning each):**
- **Sign:** what gets recorded (avoid "sign class" in the UI).
- **Sample:** one saved recording.
- **Automated check:** the technical landmark QC (avoid "QC" in UI text).
- **Human review:** any reviewer's approve, recapture or reject decision.
- **Linguistic validation:** approval by a native or Deaf signer only.
- **DEMO DATA:** synthetic samples, always in capitals and always badged.

**Do:**
- Show where every number comes from: run, split strategy, sample counts.
- Badge synthetic data every time.
- Keep QC and human review visually separate.
- Write states in words.

**Don't:**
- Use fake charts, placeholder metrics, or "live AI" indicators.
- Put an eyebrow or kicker label above a heading.
- Use emoji or glyphs as icons.
- Use gradient text.
- Show a real person's replay without approval and public-display consent.
