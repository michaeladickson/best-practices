FIRST: If review-context.md exists, read it for project context, threat model, and
intentional design decisions. Follow it strictly — do NOT flag intentional decisions.
ALSO: Read existing-issues.md — do NOT report findings already tracked there.
ALSO: Read digest-intelligence.md for emerging patterns to check against.

---

Perform a comprehensive UI/UX review of the frontend codebase. Focus on:

1. **Consistency** — Component patterns, spacing, colors, typography across all views; adherence to design tokens/theme
2. **Accessibility** — ARIA labels, keyboard navigation, focus management, color contrast, screen reader support
3. **Responsiveness** — Layout behavior at different screen sizes, overflow handling, touch targets on mobile
4. **Error States** — Loading indicators, empty states, error messages, form validation feedback, skeleton screens
5. **User Experience** — Confirmation dialogs for destructive actions, undo support, clear feedback on actions, optimistic updates
6. **Component Reuse** — Duplicated UI patterns that should use shared components, inconsistent prop interfaces

Review all UI files (.tsx, .ts) in views/pages and components directories.
Also review theme/style tokens and CSS files for consistency.

Format your findings as a markdown document with:
- Executive summary (2-3 sentences)
- Findings grouped by category (Consistency, Accessibility, Responsiveness, Error States, UX, Component Reuse)
- Within each category, assign severity (Critical, High, Medium, Low) to each finding
- Each finding should have: file, line number, severity, description, suggested fix
- Use markdown checkboxes so items can be tracked

Output ONLY the findings, no title or preamble.
