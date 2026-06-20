---
name: High-Contrast Cyber-Utilitarian
colors:
  surface: '#111317'
  surface-dim: '#111317'
  surface-bright: '#37393e'
  surface-container-lowest: '#0c0e12'
  surface-container-low: '#1a1c20'
  surface-container: '#1e2024'
  surface-container-high: '#282a2e'
  surface-container-highest: '#333539'
  on-surface: '#e2e2e8'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#e2e2e8'
  inverse-on-surface: '#2f3035'
  outline: '#849495'
  outline-variant: '#3b494b'
  surface-tint: '#00dbe9'
  primary: '#dbfcff'
  on-primary: '#00363a'
  primary-container: '#00f0ff'
  on-primary-container: '#006970'
  inverse-primary: '#006970'
  secondary: '#ffffff'
  on-secondary: '#253600'
  secondary-container: '#b6f700'
  on-secondary-container: '#4f6e00'
  tertiary: '#fff5de'
  on-tertiary: '#3b2f00'
  tertiary-container: '#fed639'
  on-tertiary-container: '#715d00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#7df4ff'
  primary-fixed-dim: '#00dbe9'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f54'
  secondary-fixed: '#b6f700'
  secondary-fixed-dim: '#9fd800'
  on-secondary-fixed: '#141f00'
  on-secondary-fixed-variant: '#374e00'
  tertiary-fixed: '#ffe179'
  tertiary-fixed-dim: '#eac324'
  on-tertiary-fixed: '#231b00'
  on-tertiary-fixed-variant: '#554500'
  background: '#111317'
  on-background: '#e2e2e8'
  surface-variant: '#333539'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
  body-lg:
    fontFamily: Atkinson Hyperlegible Next
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Atkinson Hyperlegible Next
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.4'
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The brand personality is precise, technical, and uncompromisingly accessible. It targets power users, developers, and individuals requiring high-clarity interfaces within high-stakes environments. The aesthetic merges **Cyber-Utilitarianism** with **Inclusive Design**, utilizing a dark-mode-first approach that prioritizes cognitive ease and visual ergonomics.

The design style is **High-Contrast / Modern**. It leverages a rigid structural grid, monospaced accents for technical data, and ultra-high-luminance accent colors against deep, layered surfaces. Every element is designed to minimize visual noise while maximizing the speed of recognition and interaction.

## Colors

The palette is anchored in a deep carbon neutral (`#0F1115`) to provide a stable, low-strain background for prolonged use. 

- **Primary (Cyber Cyan):** Used for primary actions and focus states. It ensures 4.5:1+ contrast against the deepest surfaces.
- **Secondary (Acid Lime):** Used for highlighting technical data or secondary callouts where high visibility is paramount.
- **Status Tokens:** Standardized high-luminance tones. Success (Green), Error (Red), and Warning (Amber) are optimized for distinct hue-separation to assist users with color-vision deficiencies.
- **Contrast Ratios:** All text-to-background combinations must meet or exceed WCAG 2.1 AA (4.5:1) for body text and AAA (7:1) for critical UI indicators where possible.

## Typography

Typography prioritizes legibility over decoration. **Geist** provides a technical, geometric foundation for headings, while **Atkinson Hyperlegible Next** is the workhorse for body content, specifically designed to differentiate between similar letterforms (e.g., I, l, 1).

**JetBrains Mono** is reserved for metadata, labels, and code-based inputs, providing a clear "utilitarian" signal to the user. The minimum font size for any metadata is 12px, with a strong preference for 14px in interactive contexts. All body text maintains a minimum line height of 1.5 to support readability.

## Layout & Spacing

This design system utilizes a **12-column fluid grid** for desktop and a **4-column grid** for mobile. The layout is built on a strict 4px/8px baseline grid to ensure vertical rhythm and alignment of technical data.

- **Desktop:** 48px outer margins with 24px gutters.
- **Mobile:** 16px outer margins with 16px gutters to maximize content area.
- **Density:** Provide "Comfortable" and "Compact" spacing modes. "Comfortable" is the default for general navigation, while "Compact" is reserved for data-heavy dashboard views.

## Elevation & Depth

Depth is achieved through **Tonal Layering** and high-contrast stroke separation rather than traditional drop shadows, which can be muddy on dark backgrounds.

- **Level 0 (Base):** `#0F1115` - The primary canvas.
- **Level 1 (Surface):** `#1A1D23` - Main content cards and panels. Separated by a 1px border (`#2D323C`).
- **Level 2 (Overlay):** `#252932` - Modals and tooltips.
- **Contrast Strokes:** Every container must have a visible border. High-luminance accents (Cyber Cyan) are used sparingly as top-border "accents" to denote active or focused panels. 
- **Backdrop:** Use a heavy backdrop blur (20px) behind modals to reduce visual noise from the level below.

## Shapes

The shape language is "Soft-Mechanical." We use a **0.25rem (4px) base radius** for all UI elements like buttons and input fields. This provides a professional, engineered feel that is more approachable than sharp corners while remaining more space-efficient than full rounds. Larger containers (cards) use **0.5rem (8px)**.

## Components

- **Buttons:** Primary buttons use a solid Cyber Cyan background with black text for maximum contrast. Secondary buttons use a high-contrast ghost style (white border, white text).
- **Focus Indicators:** Crucial for accessibility. Use a 2px offset solid stroke in Cyber Cyan (`#00F0FF`) for all keyboard focus states. Never rely on color change alone.
- **Inputs:** Fields have a dark background (`#0F1115`) with a 1px border. On focus, the border thickens to 2px and changes to the primary color.
- **Chips:** Utilized for status and filtering. They must include an icon to supplement the color-coding (e.g., an 'X' for errors, a 'Check' for success).
- **Cards:** Defined by a Level 1 surface and a mandatory 1px border. Use a "header strip" of 2px height in the accent color for active or highlighted cards.
- **Lists:** High vertical padding (12px-16px) between items to prevent accidental taps and improve scannability for low-vision users.