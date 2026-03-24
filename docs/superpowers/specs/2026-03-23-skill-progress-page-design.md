# Skill Progress Page — Design Spec

## Context

The Dashboard currently shows skill cards with overall band + exercise count. Speaking insights (criterion bars, trends, session history) were added below the grid, but on mobile users must scroll past all cards to see them — poor visibility. We need a dedicated progress page that works for speaking now and extends to all skills later.

Design principle: **less is more on mobile — concise, scannable, actionable.**

---

## Architecture

- New route: `/progress/:skill` (e.g., `/progress/speaking`)
- New page component: `frontend/src/pages/SkillProgress.tsx`
- Dashboard SkillCards become tappable links → navigate to `/progress/{skill}`
- Remove the current inline expanded panel from Dashboard
- Backend: reuse existing `GET /progress/speaking-insights` endpoint. Future skills get their own insights endpoints following the same pattern.

## Page Layout (mobile-first)

Top to bottom, no horizontal scroll:

### 1. Header
- `← Back` link (returns to Dashboard)
- Skill name as title ("Speaking Progress")

### 2. Summary Stats Row
- 3 numbers side by side: **Avg Band** | **Best** | **Sessions**
- Large font, color-coded (primary for avg, green for best)

### 3. Criterion Breakdown
- 4 rows, each: abbreviated label (FC/LR/GRA/Pron) + colored bar + band number + trend arrow
- Bar width = band/9 * 100%
- Colors: green ≥7, amber ≥6, red <6
- Trend arrows: ↑ green (improving), ↓ red (declining), → gray (stable), — gray (insufficient data)

### 4. Focus Area Callout
- Amber-bordered card showing weakest criterion + actionable recommendation
- Only shown if total_sessions > 0

### 5. Recent Sessions
- Last 5 sessions as compact rows: date + band (color-coded) + topic (truncated)
- No session history section if 0 sessions

### 6. CTA Button
- "Practice Speaking" — navigates to `/practice` (speaking pre-selected via query param or state)

### Empty State
- If 0 sessions: show a centered message + CTA button instead of all sections

## Dashboard Changes

- Remove `speakingInsights` state, `expandedSkill` state, and the `speaking-insights-panel` render block
- Remove the `onClick`/`isExpanded` props from SkillCard
- All SkillCards become `<Link to={/progress/${skill}}>` wrappers — tapping any card navigates to the progress page
- For skills without an insights endpoint yet (reading, listening, writing, grammar): the progress page shows the basic stats from `UserProgress` (band, exercises, study time) + "Detailed insights coming soon" message

## Files

| File | Change |
|------|--------|
| `frontend/src/pages/SkillProgress.tsx` | CREATE — new page component |
| `frontend/src/pages/Dashboard.tsx` | MODIFY — remove expanded panel, make cards navigable |
| `frontend/src/App.tsx` | MODIFY — add route `/progress/:skill` |

## Verification

1. `npm run build` passes
2. Dashboard → tap Speaking card → navigates to `/progress/speaking` with full breakdown
3. Dashboard → tap Reading card → navigates to `/progress/reading` with basic stats + "coming soon"
4. Back button returns to Dashboard
5. Mobile: everything visible without horizontal scroll, compact layout
