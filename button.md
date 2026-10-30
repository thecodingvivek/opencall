# Cuelume button styling

Reference: [cuelume.dev](https://cuelume.dev/), inspected from its rendered HTML and linked stylesheets. Its hero actions are links styled by an Astro-scoped button component. The inspected code does not identify a third-party button library.

## Shape and typography

- Compact rounded rectangle: 9px radius, increased to 12px when the browser supports `corner-shape: squircle`. The reference is not pill-shaped.
- Default size: 28px high, 11px horizontal padding, 12px Inter at weight 600, and 6px gap for icons.
- Hero size (`btn-lg`): 32px high, 13px horizontal padding, 13px text, and 7px gap.
- Letter spacing is slightly tight (`-0.009em`); labels remain on one line.

## Variants

| Variant | Surface | Text | Edge and shadow |
| --- | --- | --- | --- |
| Primary | Near black `#121212` | Warm white `#faf9f6` | `0 1px 2px #12121229` |
| Quiet | White `#fff` | Charcoal `#343433`, weight 500 | Inset 1px `#12121214` and subtle `0 1px 2px #1212120a` shadow |

The background is drawn on a `::before` layer behind the label. The hero uses a primary **Get started** and a quiet **Hear the cues**, arranged horizontally.

## Interaction

- On hover with a fine pointer, the primary surface changes to charcoal. The quiet button's text darkens to `#121212` and its inset border changes from `#12121214` to `#12121229`.
- Both hero buttons have a diagonal sheen that travels across the surface on hover over 0.72 seconds. The sheen is light on the dark button and dark on the light button.
- On press, the control moves down 1px and scales to 96% over 90ms using `cubic-bezier(.2, 0, 0, 1)`. The primary shadow flattens to `0 0 #12121229`; the quiet button keeps only its inset `#12121214` border. The pressed shadow overrides the hover shadow.
- On release, the position returns over 250ms using `cubic-bezier(.2, 0, 0, 1)`, while the scale returns over 500ms using the spring curve `cubic-bezier(.34, 1.56, .64, 1)` to create the bounce.
- On coarse pointers, a pseudo-element extends the vertical touch target to at least 44px without changing the visible height.
- Reduced-motion settings disable the sheen, movement, and scale animation.
- `data-cuelume-navigate` adds the Cuelume navigation sound; the sound library is separate from the visual styles.

## Adapting it for OpenCall

The home page uses the dark and quiet variants, border, shadow, sheen, and press and release timing described above. Its buttons use a `9999px` radius for the requested pill shape and extend their touch targets to 44px on coarse pointers. The controls are links and have a visible keyboard focus outline. Styling is in `frontend/src/app/globals.css`; markup is in `frontend/src/app/page.tsx`.
