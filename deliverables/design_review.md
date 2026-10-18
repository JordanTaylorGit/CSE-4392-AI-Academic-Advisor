# Design review: AI Academic Advisor (Streamlit web UI)

Reviewed 2026-10-17 with the `apple-design` skill (Apple Human Interface Guidelines).
Scope: this is a **web app**, so Apple's design principles and foundations apply
(accessibility, color, dark mode, layout, typography, writing, modality, feedback);
iOS/macOS platform conventions (tab bars, menu bar) do not.

## Summary

**Before: Critical issues. After fixes: Good.** The screen's job is to show a student
their path to graduation; the design is remembered by the **degree route**, a vertical
line where each semester is a stop (solid green = completed, hollow blue = planned),
under one segmented credit bar. Two text-contrast failures, no dark appearance, and
silent add/drop changes were the main problems; all are fixed.

## Critical (fixed)

| What | Why | Fix |
|---|---|---|
| Streamlit captions rendered ~#737C8B on #F6F8FA = **3.96:1** (small regular text needs 4.5:1) | `accessibility.md › Vision`: up to 17 pt, all weights, minimum 4.5:1 | Captions use `--ink-soft` #4A5A70 = **6.60:1** |
| Grades in completed courses: #2E7D5B on #E3F1EA = **4.29:1** at 14.7 px semibold | Same rule (semibold is not bold) | `--done` → #256B4D = **5.48:1** (6.39:1 on white) |

## Improvements (fixed)

| Tag | What | Why | Fix |
|---|---|---|---|
| High | Light appearance only | `dark-mode.md`: "Ensure that your app looks good in both appearance modes" | `[theme.light]` / `[theme.dark]` in config + dark CSS tokens following the system setting; all dark pairs ≥ 5.7:1 (below) |
| Medium | Add/drop changed the plan silently, with no way back | `feedback.md`: "confirm that a significant action or task has completed" | Toast "Added CSE 3320 to Fall 2026" + **Undo last change** button |
| Medium | After adopting a switched-major plan, header still named the old program | `writing.md`: "Be clear" | Header reads "<new program> (exploring a switch from <old>)" |
| Medium | Voice mixed "Build **my** plan" with "Ask **your** advisor" | `writing.md`: "Use possessive pronouns sparingly"; "Build language patterns" | "Build plan"; chat placeholder "Ask about courses, requirements, or the schedule…" |
| Medium | Semester names were plain spans: screen-reader users couldn't jump between semesters | `accessibility.md › Mobility`: label elements for assistive technologies (judgment for web: heading semantics) | `role="heading" aria-level="3"` on each semester |
| Medium | A developer switch ("Use preview data") sat in the student-facing sidebar | `design-principles.md` Simplicity; `writing.md` "Write for everyone" | Moved into a collapsed **For the project team** section |
| Medium | Dialog buttons "Add to plan" / "Drop from plan" didn't match the dialog titles | `writing.md`: "use consistent language throughout processes" | "Add a course" → **Add course** → "Added …"; "Drop a course" → **Drop course** → "Dropped …" |
| Low | Empty state promised "completed courses below" to students with none | `writing.md`: "Provide clear next steps on any blank screens" | Text adapts to whether there is a transcript |
| Low | Empty part of the credit bar outlined at #D5DBE3 = 1.31:1 | Judgment (WCAG 1.4.11 non-text 3:1) | Outline `--edge` #7A8597 = **3.50:1** |
| Low | No answer for Increase Contrast | `accessibility.md`: provide higher contrast when the setting is on | `@media (prefers-contrast: more)` raises secondary text to full ink and rules to the edge color |
| Low | Pending pill #B26A00 on #FBF0DD = 3.76:1 (passes 3:1 for bold, little margin) | `accessibility.md › Vision` | `--caution` → #8A5300 = **5.61:1** |

## Contrast table (WCAG ratios), current palette

Updated after the Apple/Stripe-style redesign (system type, grey canvas, white cards,
blue #0071E3 actions). The findings above were fixed in the earlier palette and carried over.

| Pair | Light | Dark |
|---|---|---|
| Body text on page | 15.46 (#1D1D1F / #F5F5F7) | 19.29 (#F5F5F7 / #000) |
| Body text on card | — | 15.63 (on #1C1C1E) |
| Secondary text on page | 4.66 (#6E6E73) | 8.16 (#A1A1A6) |
| Secondary text on card | 5.07 | 6.61 |
| White on primary button #0071E3 | 4.70 | 4.70 (same blue; #0A7AFF would be 4.01) |
| Blue text / links | 5.57 (#0066CC) | 6.48 (#4DA3FF on card) |
| Pass / grade on green tint | 4.75 | 7.25 |
| Fails on red tint | 5.30 | 5.66 |
| Caution on orange tint | 5.52 | 8.42 |
| Moved chip on blue tint | 4.88 | 5.89 |
| Non-text outlines (--edge) | 3.62 | 3.25 |

## Craft notes

The route has a clear point of view and spends the boldness in one place; everything
else is quiet. Structure carries meaning: the six checks use the assignment's own (a)–(f)
order, and solid vs hollow stops encode completed vs planned without relying on color.
Nothing left to remove without loss.

## What works (keep)

- One color, one meaning: green = completed/pass, blue = planned, amber = caution, red = fail.
- Color is never the only signal: stop shape, strike-through on removed courses, and
  text on every pill and legend item.
- `rem` sizing, so browser zoom to 200% scales everything; visible keyboard focus;
  reduced motion respected; layout collapses to one column under 640 px.

## Not verified

- Screen-reader pass with VoiceOver (headings added, not yet listened to).
- `prefers-contrast: more` was not toggled in a browser.
