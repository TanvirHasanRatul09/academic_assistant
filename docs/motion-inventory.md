# Motion inventory

This inventory is the implementation boundary for decorative and interaction motion. New motion should reuse these tokens and justify a user-facing state or hierarchy change.

| Surface | Purpose | Trigger | Duration / easing | Responsive behavior | Reduced-motion fallback |
| --- | --- | --- | --- | --- | --- |
| Route content | Preserve navigation continuity | Route mount | 340 ms, enter | Shorter distance on mobile | Content is immediately visible; no transform |
| Dialog, drawer, popover | Clarify layer hierarchy | Open | 220-380 ms, enter/spring | Drawer distance reduced on mobile | Opens immediately |
| Toast and status panel | Draw attention to feedback | Mount | 220-340 ms, enter/spring | Same timing, small travel | Appears immediately |
| Buttons, filters, cards | Confirm interaction and affordance | Hover, focus, press | 100-220 ms, standard | Hover lift only with fine pointer | Color/state changes remain; no movement |
| Assistant messages | Show conversational sequence | Message mount | 220 ms, enter | Travel reduced on mobile | Appears immediately |
| Loading skeletons | Communicate pending content | Loading | 1.5 s cycle | Same on tablet; static with reduced motion | Static placeholder |
| Welcome ambient scene | Establish calm depth without obscuring content | Page visible | 28-36 s cycles, ambient | Fewer layers on tablet; one static layer on mobile | Static low-contrast gradient |
| Onboarding ambient scene | Support step hierarchy | Page visible | 32-36 s cycles, ambient | Calmer layers and no mobile loop | Static low-contrast gradient |
| Assistant empty-state scene | Make the empty state inviting | No chat turns and page visible | 28-36 s cycles, ambient | One static layer on mobile | Static low-contrast gradient |
| Ambient pointer depth | Add subtle spatial response | Fine-pointer movement | rAF-throttled, 2-8 px | Reduced on tablet; disabled on touch/mobile | Disabled and reset |

Continuous ambient animation is intentionally excluded from dashboards, task lists, forms, and reading-heavy surfaces. `MotionController` pauses all animation when the document is hidden.
