# Ozone Studios — Design System

The theme to preserve and extend. All values match the live `styles.css` tokens; pull from those rather than re-deriving.

## Theme call

**Dark.** The scene sentence: *Egyptian artist on a phone at 1AM, deciding whether to send their vocals to this room tomorrow night.* The ambient light is the phone. The screen is the room. White surfaces would be hostile to the mood and to the audience.

## Color

Strategy: **Restrained.** Greyscale neutrals on a tinted-near-black base, one accent (`white`) reserved for surfaces that are currently doing work — the active slot, the primary CTA pill, the brand mark, the casino digit cells. White is not decoration. If a surface is white-on-dark and not earning its weight (active, selected, primary action), it's wrong.

```
Token            Value             Role
--bg             hsl(0 0% 4%)      Page background
--bg-2           hsl(0 0% 6%)      Sidebar / nav strip
--card           hsl(0 0% 7%)      Booking card, equipment card, FAQ card
--card-2         hsl(0 0% 9%)      Nested surfaces (booking-grid inner)
--border         hsl(0 0% 14%)     Default card borders
--border-2       hsl(0 0% 18%)     Inner dividers, input borders
--muted          hsl(0 0% 60%)     Body text on dark, eyebrow labels
--muted-2        hsl(0 0% 45%)     Footer copy, secondary metadata
--fg             hsl(0 0% 96%)     Primary text, headings
--primary        hsl(0 0% 96%)     Same as fg; used for active-state surfaces
--primary-fg     hsl(0 0% 4%)      Text on white surfaces
```

Status colors used in admin: greens for `DONE`, blues for `CONFIRMED`, yellows for `PENDING`, reds for `CANCELLED`. Pulled into `--status-*` tokens when needed.

Hover treatments use white-glow shadows (`rgba(255,255,255,.18)` to `.35`), never bright accent colors. Never add a hue unless the user explicitly approves it for that surface.

## Typography

Type pair: **Orbitron (display) + Space Grotesk (body).** Italic in display is achieved via Brush Script MT / Lucida Handwriting for the wordmark wordmark "Studios" sub-tag only.

```
--font-display    "Orbitron", "Space Grotesk", sans-serif
--font-body       "Space Grotesk", system-ui, sans-serif
```

Scale rules:

- Hero title: `clamp(48px, 12vw, 140px)`, weight 900, letter-spacing tight (`-.02em`).
- Section title (`.section-title`): Orbitron 800, letter-spacing `.06em`, uppercase.
- Body: Space Grotesk 400-500, line-height 1.5-1.65.
- Eyebrows (small uppercase labels): Orbitron 600-700, letter-spacing `.22em-.26em`, size 11-13px, color `--muted`.
- Buttons / nav links / studio tabs / mode tabs / slot labels: Orbitron 700-800, letter-spacing `.18em-.22em`, uppercase.

Italic display ("Studios" sub-tag): script font, never Orbitron-italic. This is the single typographic flourish in the brand. Don't add others.

Line length cap: 65-75ch for any body paragraph that runs across the full width.

## Radii

```
--radius-sm     0.5rem    Inputs, time-slot pills, small chips
--radius-md     1rem      Standard cards (about-card, work-card)
--radius-lg     1.5rem    Hero-level cards (book-form, faq card)
--radius-pill   999px     CTAs, mode tabs, studio tabs, button-pill
```

The pill radius is the brand's signature button shape — `.btn-pill` outline and solid variants are the only CTA family. Don't introduce square or sharp-corner buttons.

## Elevation

Cards layer two effects:

1. **Inset highlight at the top edge:** `inset 0 1px 0 rgba(255,255,255,.04)` — sells the "lit from above by a studio light" feel.
2. **Diffuse drop shadow with brand glow:** `0 18px 44px rgba(0,0,0,.4), 0 0 28px rgba(255,255,255,.03)` for resting; lift to `0 24px 56px rgba(0,0,0,.5), 0 0 36px rgba(255,255,255,.06)` on hover.

Never use a default Material elevation or a tinted-blur soft shadow. The glow rim and inset top highlight together are the look.

## Components

These exist in code today. Use them; don't reinvent.

### `.btn-pill` (solid / outline / lg)
The CTA family. Solid = primary action (`SUBMIT REQUEST`, `BOOK A SESSION`). Outline = secondary (`VIEW SERVICES`, `BOOK NOW` in nav). `.lg` modifier for hero CTAs. Hover lift: `translateY(-1px)` + white-glow shadow.

### `.nav` (fixed, blurred backdrop)
Height `--nav-h` (92px). Backdrop-filter blur + gradient fade. Brand on the left, link cluster centered, two CTAs (GUEST MODE button + BOOK NOW pill) on the right.

### `.streams-counter`
Wraps an `<a>` to Spotify. Slot-machine digit roll (one `.digit` cell per character of `1,000,000`, with `.comma` separators rendered between). Triggered once on scroll-into-view via IntersectionObserver. Label below in Orbitron 700, letter-spacing `.42em`. Single label word: **STREAMS**. Don't extend with subtitles.

### `.works-grid` (5-up)
`grid-template-columns: repeat(5, 1fr)`. Mixed-aspect cover images, each card linking to the release on YouTube. Drops to 2-up at 980px, single column on mobile. Hover effect: image-only scale + brightness lift.

### `.studio-tabs` and `.book-mode-tabs`
Pill-rail toggles. Two values each. Active = white background, near-black text, white glow. Inactive = transparent, muted text. Used for:
- Studio A / Studio B (calendar belongs to a single studio at a time)
- BOOK SESSION / BOOK SERVICE (two different forms)

### `.booking-grid` (3-column inside booking card)
`grid-template-columns: 1fr 1.4fr 1fr`. Studio info left, calendar center, slot list right. Collapses to single column at 980px with dividers becoming horizontal.

### Calendar (`.cal-grid`)
Custom calendar in JS. Hour-aware. Past dates dimmed and disabled. Selected date is white-on-dark, today gets a thin white border. Prev/next month arrows are 30x30 pill-bordered squares.

### Slot list (`.slot` + `.slot-custom`)
Four fixed slots (3PM-5PM, 5PM-7PM, 7PM-9PM, 9PM-11PM) + one custom-hours block with two `<select>` dropdowns offering whole-hour options from 3PM to 11PM. Active state matches active studio-tab: white surface, near-black text.

### Service options (`.service-options`)
3-up radio card row. Mix & Master, Beat, Artwork. Selected card gets white border + faint white glow. Icons are 22x22 hand-built SVGs in 42x42 squircle frames.

### `.file-drop` (kept for visual reference, currently unused)
Dashed border, centered icon + label, file-name swap on selection. Replaced in the service form by a plain `<input type="url">` for a file link, but the dropzone CSS is preserved in case attachments come back.

### `.about-card` (FAQ + Mission + Team)
Card family for the About section. `<details>`/`<summary>` with `+`/`−` indicator for FAQ rows. Mission gets italic Orbitron, larger size.

### `.team-grid`
3-up, 2-up at 980px, 1-up at 560px. Each `.team-card` has 96px circular `.team-photo`, name in Orbitron 700, role in Orbitron 600 with `.22em` letter-spacing, short bio, social-icon row at the bottom. Top border has a horizontal light-streak gradient (`linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent)`).

### `.footer`
Brand mark **above** the wordmark (column flex), centered. Social icons centered below. Copyright centered. "Powered by MeGaA" absolutely positioned bottom-right (links to a `wa.me` URL). On mobile (<720px), powered-by stacks below copy.

## Motion

- Hover lifts: `translateY(-2px)` to `translateY(-3px)` with `ease` over 200-250ms.
- Smooth scroll: custom JS animation via `requestAnimationFrame` with `easeInOutCubic`, duration 600-1400ms scaled by distance. CSS `scroll-behavior: smooth` is intentionally OFF — the JS owns the curve.
- Streams counter: ~1600ms + per-digit stagger of 220ms, `cubic-bezier(.18,.86,.24,1)`. Right-most digits land last, sequentially.
- Vinyl spin in the hero: infinite linear rotate. Headphones sway, music notes bounce.

No layout-property animations. No bounce/elastic. No fade-in-on-scroll noise.

## Spacing & layout

- Container width: `1280px` for most pages.
- Section vertical rhythm: ~80-130px top padding, ~80-100px bottom padding for hero-like sections. Booking section: 30px top, 130px bottom.
- Cards use 22-40px padding. Inner grids use 22-28px gaps.
- Booking card (`.book-form`) and About cards (`.about-card`) get the inset top highlight; raw page sections don't.

## Hard rules carried from the global skill

1. No `#000` or `#fff`. The tokens above are slightly off both extremes.
2. No gradient text, no side-stripe accent borders, no glassmorphism-as-default, no hero-metric SaaS template, no card-grid identicality, no modal-as-first-thought.
3. No em dashes in code or copy.
4. Body line-length capped at 65-75ch.
5. Hierarchy via scale + weight contrast (≥1.25 ratio between steps).

## Out of bounds without explicit approval

- Adding a non-greyscale color. The site is monochrome by deliberate choice.
- Adding a third typeface.
- Switching to a light theme, or even a dark/light toggle.
- Adding gradient overlays beyond the existing nav-fade and works-grid hover.
- Replacing the slot-machine digit counter with a smooth count-up.
