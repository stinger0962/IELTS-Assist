# Project Instructions

## Code Quality
- Do NOT sacrifice code quality for the speed of implementation
- Extract shared logic into hooks, utilities, or components — never duplicate code
- Follow DRY, YAGNI, and existing project patterns

## Data Format Awareness
- **Reading questions** use `groups` format: `{ questions: { groups: [{ type, items }] } }`
- **Listening questions** use flat format: `{ questions: { completion: [], multiple_choice: [], matching: [] } }`
- **Listening matching** has nested structure: `{ stems: [], options: [], answers: {} }` inside each matching block
- ALWAYS check the actual data format of the skill you're working with before writing frontend renderers
- ALWAYS read the generator's output format before building an orchestrator or scorer on top of it
- When building a new feature for one skill based on another skill's pattern, verify the data shapes match — do NOT assume they're identical

## Frontend Verification
- Mobile-first: test all UX on mobile viewport (430px width) before desktop
- After building any UI component, verify the actual API response matches what the component expects
- Sticky elements require `overflow-x: clip` on parent containers (not `overflow-x: hidden`)
