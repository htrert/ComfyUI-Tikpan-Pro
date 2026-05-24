# Tikpan Web Design Notes

## Positioning

Tikpan Web is an operational AI studio, not a marketing landing page. The first screen should help users choose a model, understand cost, fill parameters, and inspect results.

## Visual Language

- Use a quiet product-console layout: left model navigation, center context/result, right parameter controls.
- Keep cards compact with 6-10px radii, hairline borders, and restrained shadows.
- Use Tikpan green as the main operational accent for focus, selected states, progress, and safe actions.
- Support dark mode with the same semantic tokens rather than a separate visual system.
- Avoid decorative blobs, oversized hero sections, and one-note purple/blue gradients.

## Motion

Inspired by React Bits, motion should feel useful and light:

- Spotlight hover is allowed on selectable model cards and the active model header.
- Use short transitions, 140-220ms, for selection, advanced-field reveal, preview panels, and status changes.
- Loading states should communicate work in progress without blocking layout.
- Respect `prefers-reduced-motion`.

## Components

- Model navigation items must be keyboard reachable and searchable.
- Model header should summarize identity, provider, and category without becoming a hero card.
- Insight cards explain capability, parameter contract, and delivery path.
- The progress rail has four stable stages: select, validate, request, deliver.
- Result panel should handle image, video, audio, text, links, raw JSON, empty, loading, and error states.
- Advanced parameters stay collapsed by default; custom ID fields only appear when their trigger option requires them.

## Content Rules

- Use short Chinese labels first. Keep API terms such as `Token`, `PersonaID`, `voice_id`, `JSON`, and `HTTPS` when they help users match upstream docs.
- Every model should tell the user what to do next, not explain the entire system.
- Cost text must say "estimated" when final billing depends on backend routing.

## Implementation Guardrails

- Keep the current Flask template architecture unless the project intentionally moves to a frontend build system.
- Do not copy large external component libraries into the app. Translate patterns into small CSS/JS primitives.
- Prefer semantic CSS variables and small reusable class patterns over one-off inline styles.
- Do not introduce frontend dependencies for hover, reveal, toast, or simple search interactions.
