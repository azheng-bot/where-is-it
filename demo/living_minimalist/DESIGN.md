---
name: Codex Analytical
colors:
  surface: '#f9f9f8'
  surface-dim: '#dadad9'
  surface-bright: '#f9f9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f9f8f7'
  surface-container: '#f5f4f2'
  surface-container-high: '#f1f0ee'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#464742'
  inverse-surface: '#2f3130'
  inverse-on-surface: '#f1f1f0'
  outline: '#777872'
  outline-variant: '#c7c7c0'
  surface-tint: '#5f5e5d'
  primary: '#333332'
  on-primary: '#ffffff'
  primary-container: '#4a4948'
  on-primary-container: '#bbb8b7'
  inverse-primary: '#c9c6c4'
  secondary: '#5f5e5c'
  on-secondary: '#ffffff'
  secondary-container: '#e5e2df'
  on-secondary-container: '#656462'
  tertiary: '#333331'
  on-tertiary: '#ffffff'
  tertiary-container: '#4a4947'
  on-tertiary-container: '#bab8b6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e5e2e0'
  primary-fixed-dim: '#c9c6c4'
  on-primary-fixed: '#1c1b1b'
  on-primary-fixed-variant: '#474646'
  secondary-fixed: '#e5e2df'
  secondary-fixed-dim: '#c9c6c3'
  on-secondary-fixed: '#1c1c1a'
  on-secondary-fixed-variant: '#474745'
  tertiary-fixed: '#e5e2df'
  tertiary-fixed-dim: '#c8c6c3'
  on-tertiary-fixed: '#1c1c1a'
  on-tertiary-fixed-variant: '#474745'
  background: '#f9f9f8'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
  outline-muted: rgba(179, 177, 175, 0.3)
  ai-active: '#4a4948'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '500'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '500'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-xs:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.1em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  unit: 8px
  gutter: 24px
  margin-mobile: 20px
  margin-desktop: 64px
  container-max: 1200px
---

## Brand & Style
The brand identity is rooted in "Intelligent Observation"—a sophisticated, utilitarian aesthetic that balances the cold precision of AI with a warm, human-centric interface. The target audience includes tech-savvy homeowners and security professionals who value clarity over clutter.

The design style is **Corporate Modern with a Minimalist/Tactile edge**. It utilizes a "Fidelity" color approach where neutral tones dominate to allow high-contrast highlights (like search results or bounding boxes) to stand out. The interface feels lightweight and airy through heavy use of whitespace, but grounded by subtle borders and tonal layering rather than aggressive shadows.

## Colors
The palette is a monochromatic "warm stone" series. The primary color (#4a4948) acts as the anchor for interactive elements and key text. Backgrounds utilize a near-white (#fdfdfc) to maintain high readability.

Functional colors are used sparingly:
- **Primary:** Navigation anchors and primary call-to-actions.
- **Surface Tiers:** Multiple levels of warm greys (from #f9f8f7 to #f1f0ee) differentiate content sections without requiring heavy lines.
- **Accents:** Semantic colors like Error (#b3261e) follow standard patterns but are muted to fit the organic palette.

## Typography
The system uses **Plus Jakarta Sans** exclusively to achieve a friendly yet modern geometric feel. 

- **Display levels** use tighter letter spacing and medium weights to convey "headline" importance without being overly aggressive.
- **Body text** remains airy with generous line heights (1.5x) for maximum legibility.
- **Labels** utilize uppercase styling and increased letter spacing (tracking) for technical metadata and category headers, creating a "dashboard" look.

## Layout & Spacing
The layout follows a **Fluid Content Model** with fixed side navigation on desktop. 

- **Sidebar:** Fixed width (256px/16rem) with vertical rhythmic spacing of 24px (gutter).
- **Canvas:** The main content area is centered within a 1200px max-width container.
- **Grid:** Use a soft 8px grid for internal component padding and a larger 24px gutter for block-level separation.
- **Responsive:** On mobile, margins shrink to 20px, the sidebar hidden behind a hamburger menu, and display typography scales down by ~33%.

## Elevation & Depth
Depth is created primarily through **Tonal Layering** and **Low-Contrast Outlines**.

- **Level 0 (Base):** `#fdfdfc` (Background).
- **Level 1 (Cards/Inputs):** `#ffffff` with a subtle `shadow-sm` (0 2px 8px rgba(0,0,0,0.03)) and a 1px border in `outline-muted`.
- **Level 2 (Overlays):** Use backdrop-blur (12px) with semi-transparent surfaces (90% opacity) for floating controls on top of imagery.
- **Interaction:** Hover states should transition the background to `surface-container-low` rather than increasing shadow depth, maintaining a flat, architectural feel.

## Shapes
The system uses a **Pill-shaped (Level 3)** philosophy for interactive elements to feel approachable and "human."

- **Buttons & Inputs:** Fully rounded (rounded-full) to create a distinct signature look.
- **Containers/Cards:** Large radii (1rem to 2rem) ensure that even data-heavy blocks feel soft.
- **Annotations:** Technical bounding boxes use a sharper 8px radius to denote "system-generated" precision against the softer UI.

## Components
- **Buttons:** Primary buttons are solid `primary` with `on-primary` text. Secondary buttons use `surface-container` with a thin border. All use `label-sm` for text.
- **Search Input:** An oversized, fully rounded bar with centered icons and `headline-md` text. It features a subtle internal shadow to indicate "recessed" depth.
- **Result Cards:** Use a top-down information hierarchy: Large display text followed by body-lg subtext, separated by a thin divider.
- **Confidence Meters:** Horizontal progress bars using a thick 2px track with a semi-transparent primary fill.
- **Status Badges:** Small pill shapes with a pulsing dot icon and `label-xs` uppercase text.
- **AI Annotations:** Bounding boxes should be `primary` at 8% opacity with a 1px solid border to highlight objects without obscuring the source image.