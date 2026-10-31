# Ozone Studios

Cairo's premier recording facility. Marketing site and admin panel for a working recording studio.

## Register

**Brand.** This is a marketing surface where the design is the product. Visitors land here to decide whether to book a session, send work for mix/master/artwork, or browse beats. The site has to feel like the studio itself: serious, dark, hardware-respecting, casino-glam.

## Users

Egyptian rappers, singers, and producers — mostly 18-30. Mobile-first, WhatsApp-native. They want to:

- See who the studio has worked with (artists, releases) before trusting it with their money or vocals.
- Pick a room (Studio A or Studio B), a date, and a 2-hour evening slot, then start a conversation on WhatsApp.
- Send stems or briefs for an off-site service (Mix & Master, Beat, Artwork) via a link.
- Browse the team and the equipment list to confirm the gear and people are real.

Decisions usually start on a phone, often late at night. Many will only commit on WhatsApp, not via a form alone.

## Product Purpose

> "To provide high-quality audio production and creative support for emerging artists to help them reach their full potential."

## Strategic principles

1. **WhatsApp is the close.** Every form submit opens `wa.me/<studio>` with the booking pre-filled in the message. The form persists data to Firestore for the admin, but the human handoff happens in chat. Don't redesign this into a pure form-then-confirmation-email flow; the audience doesn't trust forms.
2. **Hardware is credibility.** The equipment list (Rode NT1-A, UA Volt 276, PreSonus Eris E5 in Studio A; Neumann TLM-103, UA Apollo Twin, Yamaha HS8 in Studio B) is not flavor text. It's the trust signal. Show it.
3. **One studio, two rooms.** Studio A and Studio B are first-class entities, not a "room" dropdown buried in a form. Each has its own calendar, equipment list, and selected time-slot state.
4. **Evening-only by default.** The four canonical slots are 3PM-5PM, 5PM-7PM, 7PM-9PM, 9PM-11PM. Plus a "Custom hours" option restricted to 3PM-11PM whole hours. Mornings are not a thing here.
5. **Egyptian Pound (EGP) and Arabic-comfortable.** Pricing in EGP. Copy stays English for now but never visually conflicts with future Arabic — no English-only ornament, no left-anchored decorations.
6. **The admin is one person.** Email + password login, single hard-coded admin email, real-time Firestore listeners so new bookings appear without refresh.

## Anti-references (keep the theme)

The current theme is the anti-reference: anything that **does not** look like this is wrong.

- Near-black backgrounds tinted toward zero chroma, not pure `#000`.
- Orbitron display + Space Grotesk body. No serifs. No "studio-website-rounded-soft-sans".
- White (`hsl(0 0% 96%)`) as the only "color", used sparingly for surfaces that are doing real work (active slot, primary CTA, brand mark). Everything else is on the muted greyscale ramp.
- Glow-rim shadows, not soft drop shadows. Inset highlights at the top of cards (`inset 0 1px 0 rgba(255,255,255,.04)`). Slot-machine roller for the million-streams counter.
- No SaaS-cream pastel anything. No coral-and-teal. No purple gradients. No 3D blobs.
- No card grid identicality. Mixed widths, mixed heights, mixed roles.
- No glassmorphism as default decoration. The bookng card, the booking-mode tabs, the studio tabs — solid, opaque, with restrained inset highlights.

## Non-goals

- Public-facing beats marketplace. Removed from the site. The admin still tracks beats internally for future use, but `BROWSE BEATS` is intentionally gone from the public nav and homepage.
- Multi-tenant or multi-studio. One studio, one admin, one WhatsApp number.
- Self-serve payment. Bookings are confirmed by the studio over WhatsApp. The site does not take money.
