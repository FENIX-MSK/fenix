# Spine Pair Review — fenix (inline, run by the authoring agent; not an independent subagent)

## Overall verdict
Visual identity is fully committed (tokens, contrast, light/dark pairs) and the core guest/staff loop is specified. Gaps: key flows cover 3 of 9 source journeys, several components used in EXPERIENCE.md have no visual spec, and a few surfaces lack error/empty states.

## 1. Flow coverage — thin
Checked UJ-1…UJ-9 from PRD against Key Flows.
### Findings
- **high** UJ-2, UJ-3, UJ-6, UJ-7, UJ-8, UJ-9 have no Key Flow (EXPERIENCE.md › Key Flows). *Fix:* add short flows with protagonist, climax and failure path.

## 2. Token completeness — adequate
### Findings
- **medium** Components reference light tokens only; rule for dark pairs implicit (DESIGN.md frontmatter). *Fix:* state that every `x` token switches to `x-dark` under Telegram dark scheme.

## 3. Component coverage — thin
### Findings
- **high** Used in EXPERIENCE.md without DESIGN.md spec: status steps, promo banner, active-order bar, quantity stepper, bottom nav (staff), skeleton, connection banner, cancel-reason sheet. *Fix:* add visual specs and tokens.

## 4. State coverage — adequate
### Findings
- **medium** Missing: checkout validation (no phone/consent), slot unavailable, photo upload progress/failure, invite link invalid, editor save failure. *Fix:* add rows to State Patterns.

## 5. Visual reference coverage — strong
imports/ and mockups/ linked inline; spines-win-on-conflict stated.

## 6–8. Bloat, inheritance, shape — strong
Canonical DESIGN.md order kept; EXPERIENCE.md defaults present; UJ names match PRD.

## Mechanical notes
- Component names consistent between files after fixes.
