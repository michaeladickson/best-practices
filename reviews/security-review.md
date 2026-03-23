Perform a focused security audit of this codebase. Focus on:

1. **Authentication** — Token validation on all routes, session management, password policies, MFA gaps
2. **Authorization** — Role-based access control enforcement, privilege escalation paths, missing permission checks
3. **Injection** — SQL injection (parameterized queries?), XSS (input sanitization?), command injection, template injection
4. **Secrets** — Hardcoded credentials, secrets in logs, .env committed, API keys in client-side code, secrets in error messages
5. **Data Exposure** — Sensitive data in responses (PII, tokens, internal IDs), verbose error messages, debug endpoints in production
6. **Dependencies** — Known CVEs in dependencies, outdated packages, unnecessary permissions
7. **Transport** — HTTPS enforcement, CORS configuration, cookie flags (Secure, HttpOnly, SameSite)
8. **Cryptography** — Weak algorithms, insufficient key lengths, plaintext storage of tokens/passwords
9. **Rate Limiting** — Missing rate limits on auth endpoints, API abuse vectors, DDoS surface area
10. **Supply Chain** — Third-party API trust boundaries, webhook validation, OAuth state parameter checks

Review all source files and configuration files.

Format your findings as a GitHub issue body with:
- Executive summary with risk assessment
- Findings grouped by severity (Critical, High, Medium, Low)
- Each finding should have: file, line number, OWASP category, description, remediation steps
- Use markdown checkboxes so items can be tracked
- Include a "Quick Wins" section for easy fixes

Output ONLY the issue body content, no title or extra text.
