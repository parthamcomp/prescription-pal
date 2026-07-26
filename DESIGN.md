---
name: Prescription Assistant
description: A local, private family prescription chart — bright, calm, and precise.
colors:
  bg: "#f5f7fb"
  surface: "#ffffff"
  surface-2: "#eef1f8"
  border: "#e3e7f0"
  border-strong: "#cdd3e2"
  ink: "#1b2029"
  ink-dim: "#5c6474"
  ink-faint: "#6b7280"
  amber: "#f5a524"
  amber-dark: "#dc8f10"
  amber-soft: "#fef2df"
  amber-ink: "#7a5605"
  teal: "#12b3a3"
  teal-soft: "#e0f8f5"
  teal-ink: "#086b60"
  violet: "#7c5cff"
  violet-soft: "#efeaff"
  violet-border: "#e2d9ff"
  violet-ink: "#4a2fd6"
  danger: "#b42318"
  danger-soft: "#fdecea"
  danger-border: "#f6c6bd"
typography:
  ui:
    fontFamily: "Sora, system-ui, sans-serif"
    fontWeight: 400
    lineHeight: 1.55
  ui-heading:
    fontFamily: "Sora, system-ui, sans-serif"
    fontWeight: 700
    letterSpacing: "-0.01em"
  data:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontWeight: 400
rounded:
  sm: "10px"
  md: "16px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.amber}"
    textColor: "#241a02"
    rounded: "{rounded.pill}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.amber-dark}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-dim}"
    rounded: "{rounded.pill}"
    padding: "9px 16px"
  nav-tab-active-ask:
    backgroundColor: "{colors.violet-soft}"
    textColor: "#4a2fd6"
    rounded: "{rounded.sm}"
  nav-tab-active-records:
    backgroundColor: "{colors.teal-soft}"
    textColor: "#086b60"
    rounded: "{rounded.sm}"
  nav-tab-active-upload:
    backgroundColor: "{colors.amber-soft}"
    textColor: "#7a5605"
    rounded: "{rounded.sm}"
---

# Design System: Prescription Assistant

## Overview

**Creative North Star: "The Family Chart"**

The product is a household's own private prescription record, not a chatbot with a health-app skin. Its visual system reads as a bright, tabbed record: distinct labeled sections (Ask, Records, Upload) the way a family binder has labeled dividers, rendered in clean modern surfaces rather than literal paper texture. Three bright, distinct hues identify the sections — violet for Ask, teal for Records, amber for Upload — with amber carrying the brand mark and every primary action across the whole app. Everything else stays quiet: white surfaces, soft cool-gray neutrals, no gradients, no dark mode as a default identity.

This direction replaced an earlier "medical chart" concept executed in manila and clinical red; that palette was explicitly rejected for feeling dark and institutional. The rejection is durable: no red as a brand or primary-accent color, no cream/manila/tan grounds. Red is reserved strictly for error/danger semantics, never for identity or primary actions.

**Key Characteristics:**
- Bright white surfaces on a soft cool-gray page background — never cream, tan, or dark.
- One brand accent (amber) for primary actions and the mark; violet and teal are section-identity colors only, never primary-action colors.
- One UI type family (Sora) carries every weight of hierarchy; a monospace (IBM Plex Mono) is reserved strictly for chart data — dates, dosages, drug names — never for decoration.
- Soft, generous rounding (pills for actions and chips, 16px cards) — friendly without being childish.
- Chat renders as dated, sourced "chart entries," not chat bubbles with a personality.

## Colors

A bright, restrained palette: white and soft cool-gray neutrals carry the surface; one warm amber is the only color used for action; violet and teal exist solely to identify the Ask and Records sections and their related accents (the user's own message, source citations).

### Primary
- **Marigold Amber** (`#f5a524`): the brand mark, every primary button, the Upload section's identity, and the composer's send control. Hover state **Amber Dark** (`#dc8f10`). Tint **Amber Soft** (`#fef2df`) fills the active Upload tab and the empty-state icon backdrop.

### Secondary
- **Chart Teal** (`#12b3a3`): the Records section's identity color, saved-record initial badges, and every RAG source-citation tag. Tint **Teal Soft** (`#e0f8f5`).

### Tertiary
- **Signal Violet** (`#7c5cff`): the Ask section's identity color and the caregiver's own chat entry background. Tint **Violet Soft** (`#efeaff`) with border **Violet Border** (`#e2d9ff`); also used as the focus-ring color on form inputs.

### Neutral
- **Paper White** (`#ffffff`): every card, rail, and panel surface.
- **Cool Mist** (`#f5f7fb`): the page background behind surfaces.
- **Mist Fill** (`#eef1f8`): input fills, hover backgrounds, the dashed medication editor well.
- **Border Hairline** (`#e3e7f0`) / **Border Strong** (`#cdd3e2`): card and divider borders; strong for input borders and dashed section edges.
- **Ink** (`#1b2029`): primary text. **Ink Dim** (`#5c6474`): secondary text, labels. **Ink Faint** (`#6b7280`): placeholders, timestamps, footer text.

### Named Rules
**The No-Red Rule.** Red (`#b42318`) exists only to mean "something is wrong" — validation errors, failed loads, destructive-hover states. It never appears as a brand, accent, or decorative color; a red button or red section identity is always a bug, not a choice.

**The One Accent Rule.** Amber is the only color allowed to mean "act on this." Violet and teal identify content and sections; they never appear on a primary call-to-action button.

## Typography

**UI Font:** Sora (with system-ui, sans-serif fallback)
**Data Font:** IBM Plex Mono (with ui-monospace, monospace fallback)

**Character:** One warm, rounded grotesque carries every weight of UI hierarchy — headings are the same family as body text, distinguished by weight and size, not by switching faces. The mono face is reserved for record data and small utility/status text — never for branding, headings, or prose.

### Hierarchy
- **Section title** (700, 16–17px, 1.2 line-height): the topline heading per view ("Ask", "Records", "Upload").
- **Card/entry title** (700, 14.5px): doctor names, card headers.
- **Body** (400, 14–14.5px, 1.55 line-height): chat entries, complaint/diagnosis text, form values.
- **Label** (700, 11–11.5px, `ink-dim`): field labels and section sub-headers, set in the UI face, sentence case (not tracked uppercase — this product doesn't use an eyebrow/label system elsewhere, so one shouldn't appear only on forms).
- **Data & utility** (mono, 400/600, 10–12.5px): dates, dosages, drug names, medication table cells, entry timestamps, the "local & private" stamp badge, and the composer/rail footer notes. Never the brand tagline, headings, or button/label copy.

### Named Rules
**The One Family Rule.** Sora carries every UI heading, label, body, and branding string; a second UI-text face never appears. IBM Plex Mono is the only exception, and only for the data/utility class listed above — never decoration, never brand copy.

## Layout

Two-region shell: a fixed-width rail (236px) for section navigation on the left, and a flexible main region for content. Below 860px, the rail collapses into a horizontal top bar with the tabs scrolling inline; the rail's footer note is dropped at that width rather than wrapped.

Ask is a full-height chat column: a scrolling thread capped at 680px wide and centered, with a pinned composer bar at the bottom. Records and Upload are scrolling document pages capped at 780px wide and centered, padded generously (24–30px) from the viewport edge.

Spacing rhythm: 4px steps at the tightest (icon-to-label gaps), 8–10px between related controls, 16px between form fields and card sections, 24px+ between major regions. More space sits above a heading than below it.

## Elevation & Depth

Mostly flat: cards and the rail sit on soft, low-contrast shadows rather than borders alone, giving a gentle sense of surfaces resting on the page without looking "lifted" or glassy. Depth increases only for floating/interactive elements (the composer bar, quick-suggestion chips) since they sit above the scrolling content.

### Shadow Vocabulary
- **shadow-sm** (`0 1px 2px rgba(27,32,41,0.06)`): resting cards, record entries, suggestion chips.
- **shadow** (`0 8px 20px rgba(27,32,41,0.08), 0 2px 6px rgba(27,32,41,0.05)`): the composer bar and any surface that visually floats over content.

### Named Rules
**The Soft Rest Rule.** Nothing at rest uses a shadow stronger than `shadow-sm`. A heavier shadow always means "this is floating above the page," never decoration on a static card.

## Shapes

Rounded and friendly without being playful: 16px radius on cards and panels, 10px on inputs and small controls, full pill (999px) on every button, chip, active-tab background, and the composer bar itself. No sharp corners anywhere in the UI; no colored left/right border accents on cards — section and status identity is carried by a tinted background fill or a small dot/badge, never a border stripe.

## Components

### Buttons
- **Shape:** full pill (999px radius).
- **Primary:** amber fill (`#f5a524`), ink-on-amber text (`#241a02`), 9px/16px padding, 700 weight. Hover darkens to `#dc8f10`.
- **Ghost:** white fill, `border-strong` 1px border, `ink-dim` text; hover text goes to `ink` and border darkens. Used for Refresh, Delete, Cancel, Enter-manually.

### Chips (quick-suggestion stamps, source tags)
- **Quick-suggestion chip:** pill, white background, hairline border, `shadow-sm`; hover border and text shift to violet (this is the Ask surface's identity color).
- **Source tag:** pill, `teal-soft` background, dark-teal text (`#086b60`) — always teal regardless of which section renders it, since it always means "this came from a saved record."

### Cards / Containers
- **Corner style:** 16px radius, `shadow-sm`, 1px `border` hairline.
- **Background:** white surface on the `cool-mist` page.
- **Record card header:** a 34px rounded-square initials badge (`teal-soft` fill, dark-teal text) replaces a colored border-left as the card's only color accent.

### Inputs / Fields
- **Style:** `mist-fill` background, `border-strong` 1px border, 10px radius.
- **Focus:** border shifts to violet with a 3px `violet-soft` ring — the one place violet appears outside the Ask surface, deliberately, since it reads as "attention here" everywhere in the app.
- **Medication row editor:** a dashed `border-strong` well (`mist-fill` background) containing mono-set inputs, visually distinct from the surrounding solid-bordered form fields.

### Navigation
- Rail buttons are full-width, left-aligned, 10px-radius rows with a small color dot (violet/teal/amber) plus label. Default state is transparent with `ink-dim` text; hover fills `mist-fill`; the active tab fills its section's soft tint color and sets text to that color's dark variant — never an underline or border accent.
- Collapses to a horizontal scrolling strip below 860px; the dot + tinted-fill active state persists unchanged.

## Do's and Don'ts

### Do:
- **Do** keep amber as the only "act on this" color; every primary button and the brand mark stay amber.
- **Do** use violet and teal exclusively as section/content identity (Ask, the user's own chat entries, Records, source citations) — never as button fills.
- **Do** set dates, dosages, drug names, and timestamps in IBM Plex Mono; everything else stays in Sora.
- **Do** carry a card or tab's color identity via a tinted background fill or small dot, never a border stripe.

### Don't:
- **Don't** introduce red, manila, cream, or dark-mode-as-default — this direction was chosen specifically to replace that palette.
- **Don't** add a colored `border-left`/`border-right` accent to cards, list items, or callouts.
- **Don't** use the mono face for branding, headings, or button/label copy — it's reserved for record data and small status/utility text only (no "technical" decoration).
- **Don't** add a second UI display face; hierarchy comes from weight and size within Sora.
