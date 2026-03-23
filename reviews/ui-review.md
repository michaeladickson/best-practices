Perform a comprehensive UI/UX review of the frontend codebase. Focus on:

1. **Consistency** — Component patterns, spacing, colors, typography across all views; adherence to design tokens/theme
2. **Accessibility** — ARIA labels, keyboard navigation, focus management, color contrast, screen reader support
3. **Responsiveness** — Layout behavior at different screen sizes, overflow handling, touch targets on mobile
4. **Error States** — Loading indicators, empty states, error messages, form validation feedback, skeleton screens
5. **User Experience** — Confirmation dialogs for destructive actions, undo support, clear feedback on actions, optimistic updates
6. **Component Reuse** — Duplicated UI patterns that should use shared components, inconsistent prop interfaces

Review all UI files (.tsx, .vue, .svelte, .swift, etc.) in views/pages and components directories.
Also review theme/style tokens for consistency.

Format your findings as a markdown document with:
- Executive summary (2-3 sentences)
- Findings grouped by category (Consistency, Accessibility, UX, etc.)
- Each finding should have: file, line number, description, suggested fix
- Use markdown checkboxes so items can be tracked

Output ONLY the findings, no title or preamble.
