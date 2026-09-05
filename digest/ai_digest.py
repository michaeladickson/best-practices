"""
digest/ai_digest.py
Configurable AI community digest — fetches RSS feeds, analyzes with Gemini,
scores relevance to a project context, and generates recommendations.

Feeds and project context are loaded from YAML config files, making this
reusable across projects.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import mktime
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
import feedparser
import structlog
import yaml
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = structlog.get_logger()

CONFIG_DIR = Path(__file__).parent / "config"


def _load_feeds(feeds_path: Optional[str] = None) -> list[dict]:
    path = Path(feeds_path) if feeds_path else CONFIG_DIR / "feeds.yaml"
    with open(path) as f:
        return yaml.safe_load(f)["feeds"]


def _load_context(context_path: Optional[str] = None) -> dict:
    path = Path(context_path) if context_path else CONFIG_DIR / "context-engineering.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def _build_context_prompt(ctx: dict) -> str:
    """Build the project context section of the prompt from config."""
    return f"""You are advising the owner of a project called "{ctx.get('project_name', 'unknown')}".

Description: {ctx.get('description', '')}

Tech stack: {ctx.get('tech_stack', '')}

Current AI usage:
{ctx.get('current_ai_usage', '')}

Key areas:
{ctx.get('key_areas', '')}

The owner is interested in:
{ctx.get('interests', '')}
{_recommendation_guidance_block(ctx)}"""


def _recommendation_guidance_block(ctx: dict) -> str:
    """Optional per-context override of how recommendations should be framed.

    Lets a mature target (crumbl-ops) demand narrow implementation deltas while
    a younger one keeps the default project-level framing. Appended to the
    context section so it sits with the rest of the project-specific text.
    """
    guidance = ctx.get("recommendation_guidance", "").strip()
    if not guidance:
        return ""
    return f"""
Recommendation guidance for this project (OVERRIDES the generic rules below
where they conflict):
{guidance}
"""


# Per-request cap on Gemini calls. A hung generate_content() has no client-side
# timeout by default, so on 2026-07-17 the command-center analysis stalled
# indefinitely and Task Scheduler's ExecutionTimeLimit killed the whole run —
# taking the wealth-mgmt digest, the practice update, and the git commit with it.
# Observed analysis times are 40-105s (209s worst case), so 5 min is generous
# while still bounded. Set on the client, so practice_updater's calls inherit it.
GEMINI_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", 5 * 60 * 1000))


def _get_gemini_client():
    from google import genai
    from google.genai import types

    http_options = types.HttpOptions(timeout=GEMINI_TIMEOUT_MS)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        return genai.Client(api_key=api_key, http_options=http_options)
    project = os.environ.get("GCP_PROJECT_ID", "")
    if not project:
        raise ValueError("Set GCP_PROJECT_ID in .env or provide GEMINI_API_KEY")
    return genai.Client(vertexai=True, project=project, location="us-central1",
                        http_options=http_options)


ARCHIVE_DIR = Path(__file__).parent.parent / "data" / "feed_archive"


def _load_archive() -> dict:
    """Load the post archive. Keys are URLs (dedup)."""
    archive_path = ARCHIVE_DIR / "posts.json"
    if archive_path.exists():
        with open(archive_path) as f:
            return json.load(f)
    return {}


def _save_archive(archive: dict):
    """Persist the post archive."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / "posts.json"
    with open(archive_path, "w") as f:
        json.dump(archive, f, indent=2, default=str)
    log.info("archive_saved", posts=len(archive))


# Fraction of feeds that must fail before a run is treated as broken rather
# than quiet. Every historical run fetched 100-129 posts across 33 feeds, so a
# majority-failure is an outage, not a slow news week.
FEED_FAILURE_THRESHOLD = float(os.environ.get("FEED_FAILURE_THRESHOLD", "0.5"))

# Days since a feed's newest entry before we call it stale. A fetch-level check
# cannot tell a dead feed from a quiet one — The Diff resolved fine and returned
# entries for ~3.7 years after its public feed froze in Nov 2022, and an
# abandoned Substack archive for FinTech Takes looked equally healthy. Only
# entry recency separates the two. This warns; it never fails the run, because a
# low-cadence source is legitimate. Feeds that are genuinely quiet by nature can
# set `max_quiet_days` in feeds.yaml to opt out of the noise.
FEED_STALE_DAYS = int(os.environ.get("FEED_STALE_DAYS", "90"))


def _feed_failure_reason(parsed) -> Optional[str]:
    """Return a failure reason for a parsed feed, or None if it looks healthy.

    feedparser.parse() does NOT raise on HTTP or DNS errors — it returns a
    result object with `bozo` set and `entries` empty. Verified 2026-07-19:
      404 on a live host  -> bozo=1,    status=404,  entries=0
      unresolvable host   -> bozo=True, status=None, entries=0 (URLError)
      HTML instead of XML -> bozo=1,    status=200,  entries=0
    So a try/except around parse() detects essentially nothing, which is why
    a total feed outage previously looked identical to a quiet week.

    A feed that returned entries is healthy even if bozo is set — bozo fires on
    benign encoding quirks in feeds that parse fine.
    """
    if parsed.entries:
        return None
    status = getattr(parsed, "status", None)
    if status is not None and status >= 400:
        return f"http_{status}"
    if getattr(parsed, "bozo", False):
        exc = getattr(parsed, "bozo_exception", None)
        return f"parse_error:{type(exc).__name__}" if exc is not None else "parse_error"
    # 200, well-formed, genuinely no entries — unusual but not a failure.
    return None


def _fetch_feeds(feeds: list[dict], days: int = 7) -> tuple[list[dict], dict]:
    """Fetch feeds. Returns (posts, stats) where stats reports per-feed health."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    posts = []
    archive = _load_archive()
    new_archived = 0
    failed: list[dict] = []
    stale: list[dict] = []
    ok = 0
    now = datetime.now(timezone.utc)

    for feed_info in feeds:
        newest = None
        try:
            feed = feedparser.parse(feed_info["url"])
            reason = _feed_failure_reason(feed)
            if reason:
                failed.append({"source": feed_info["name"], "reason": reason})
                log.warning("feed_fetch_failed", source=feed_info["name"], reason=reason)
                continue
            for entry in feed.entries:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=timezone.utc
                    )
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime.fromtimestamp(
                        mktime(entry.updated_parsed), tz=timezone.utc
                    )

                if not published:
                    continue

                # Track across ALL entries, not just those inside the lookback
                # window — that's the whole point of the staleness check.
                if newest is None or published > newest:
                    newest = published

                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    content = entry.summary or ""

                if len(content) > 3000:
                    content = content[:3000] + "..."

                link = entry.get("link", "")
                post = {
                    "source": feed_info["name"],
                    "category": feed_info.get("category", ""),
                    "title": entry.get("title", "Untitled"),
                    "link": link,
                    "published": published.strftime("%Y-%m-%d"),
                    "content_preview": content,
                }

                # Archive every post we see (dedup by URL)
                if link and link not in archive:
                    archive[link] = post
                    new_archived += 1

                # Only return posts within the lookback window
                if published >= cutoff:
                    posts.append(post)

            source_count = len([p for p in posts if p["source"] == feed_info["name"]])
            log.info("feed_fetched", source=feed_info["name"], posts_found=source_count)
            ok += 1

            # Resolving is not the same as alive. Warn only — a low-cadence
            # source is legitimate, so this never changes the exit code.
            limit = feed_info.get("max_quiet_days", FEED_STALE_DAYS)
            if newest is not None:
                age = (now - newest).days
                if age > limit:
                    stale.append({"source": feed_info["name"], "days": age})
                    log.warning("feed_stale", source=feed_info["name"],
                                days_since_newest=age, threshold=limit)
        except Exception as e:
            failed.append({"source": feed_info["name"], "reason": type(e).__name__})
            log.warning("feed_fetch_failed", source=feed_info["name"], error=str(e))

    # Persist archive
    if new_archived > 0:
        _save_archive(archive)
        log.info("new_posts_archived", count=new_archived)

    posts.sort(key=lambda p: p["published"], reverse=True)
    stats = {"total": len(feeds), "ok": ok, "failed": failed, "stale": stale}
    log.info("total_posts_fetched", count=len(posts),
             feeds_ok=ok, feeds_failed=len(failed), feeds_stale=len(stale),
             feeds_total=len(feeds))
    return posts, stats


def _fetch_recent_posts(feeds: list[dict], days: int = 7) -> list[dict]:
    """Posts-only wrapper. Kept for callers that don't inspect feed health
    (practice_updater, backfill)."""
    posts, _ = _fetch_feeds(feeds, days=days)
    return posts


def fetch_all_archived_posts() -> list[dict]:
    """Return all posts from the archive (for re-running analysis against full history)."""
    archive = _load_archive()
    posts = list(archive.values())
    posts.sort(key=lambda p: p.get("published", ""), reverse=True)
    return posts


INBOX_DIR = Path(__file__).parent.parent / "data" / "digest_inbox"


def _load_inbox_posts(archive: dict) -> list[dict]:
    """One-off inputs (video transcripts, pasted articles, PDFs-as-text) dropped
    into data/digest_inbox/*.md flow through the same scoring/knowledge/practice
    path as feed posts. Frontmatter: title, source_url; optional date, category,
    source. Non-destructive — the wrapper moves files to processed/ only after
    ALL contexts have run, so every digest sees them; the archive (keyed by
    source_url) dedups re-reads. See CLAUDE.md "Running the Digest".
    """
    if not INBOX_DIR.exists():
        return []
    posts = []
    for path in sorted(INBOX_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("inbox_read_failed", file=path.name, error=str(e))
            continue
        meta, body = {}, text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    body = parts[2]
                except yaml.YAMLError:
                    pass
        link = meta.get("source_url", f"inbox://{path.name}")
        post = {
            "source": meta.get("source", "Manual inbox"),
            "category": meta.get("category", "inbox"),
            "title": meta.get("title", path.stem.replace("-", " ")),
            "link": link,
            "published": str(meta.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")))[:10],
            "content_preview": body.strip()[:3000],
        }
        posts.append(post)
        if link not in archive:
            archive[link] = post
    if posts:
        _save_archive(archive)
        log.info("inbox_posts_loaded", count=len(posts))
    return posts


def _analyze_posts(posts: list[dict], context_prompt: str,
                   project_name: str) -> Optional[dict]:
    if not posts:
        return None

    client = _get_gemini_client()

    posts_text = ""
    for i, post in enumerate(posts, 1):
        posts_text += f"\n--- Post {i} ---\n"
        posts_text += f"Source: {post['source']} [{post['category']}]\n"
        posts_text += f"Title: {post['title']}\n"
        posts_text += f"Date: {post['published']}\n"
        posts_text += f"URL: {post['link']}\n"
        posts_text += f"Content:\n{post['content_preview']}\n"

    prompt = f"""Analyze these recent AI/engineering blog posts for relevance to a specific project.

{context_prompt}

Here are the posts from the past week:
{posts_text}

Return a JSON object with this structure:
{{
  "top_posts": [
    {{
      "title": "...",
      "source": "...",
      "url": "...",
      "relevance_score": 1-10,
      "summary": "2-3 sentence summary focused on what's actionable",
      "why_relevant": "1 sentence on why this matters for {project_name}"
    }}
  ],
  "project_recommendations": [
    {{
      "title": "Short imperative title (under 80 chars)",
      "recommendation": "Specific, actionable suggestion for {project_name}",
      "inspired_by": "Which post(s) inspired this",
      "effort": "small|medium|large",
      "impact": "Description of expected impact",
      "where_it_fits": "Likely module / area of {project_name} where this would slot in (it's OK to speculate based on the project description)",
      "first_step": "The smallest concrete first step to validate this idea",
      "risks": "Honest risks or tradeoffs to consider"
    }}
  ]
}}

Rules:
- Only include posts with relevance_score >= 5
- Rank top_posts by relevance_score descending, max 5 posts
- Generate 2-4 project_recommendations based on themes across the posts
- Recommendations should be specific to {project_name}, not generic AI advice
- If a post is paywalled/truncated, score based on what's visible
- For where_it_fits, first_step, risks: be concrete but acknowledge uncertainty
- Be honest — if nothing is relevant this week, return empty arrays"""

    # Force JSON at the API level rather than trusting the prompt's "respond with
    # JSON" instruction. On 2026-09-04 the crumbl-ops context came back malformed at
    # char 7885 and failed the whole weekly digest; the same fix is already house
    # practice in command-center's agents/shared/gemini_client.py for the same reason.
    config = {"response_mime_type": "application/json"}

    # One retry. A malformed response is a sampling accident, not a deterministic
    # failure, and the cost of the retry is one Flash call against a weekly job whose
    # only other outcome is a red task for seven days.
    for attempt in (1, 2):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
        except Exception as e:
            # Timeout (GEMINI_TIMEOUT_MS) or transport error. Return None so main()
            # exits non-zero and the wrapper counts this context as failed, rather
            # than raising a traceback through click.
            log.error("analysis_request_failed", error=str(e),
                      error_type=type(e).__name__, attempt=attempt)
            if attempt == 2:
                return None
            continue

        text = response.text or ""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            # Log the TAIL as well as the head. The 9/04 failure was at char 7885 and
            # the log captured only the first 200 characters, which showed a
            # well-formed opening and said nothing about what actually broke.
            log.error("json_parse_failed", error=str(e), attempt=attempt,
                      length=len(text), head=text[:200], tail=text[-300:])
            if attempt == 2:
                return None

    return None


def _build_email(analysis: dict, week_label: str,
                 project_name: str) -> tuple[str, str, str]:
    top_posts = analysis.get("top_posts", [])
    recommendations = analysis.get("project_recommendations", [])

    subject = f"AI Digest ({project_name}) — {week_label} — {len(top_posts)} posts, {len(recommendations)} recommendations"

    # Text body
    text_lines = [f"AI Best Practices Digest — {project_name} — {week_label}\n"]
    if top_posts:
        text_lines.append("TOP POSTS:")
        for p in top_posts:
            text_lines.append(f"\n  [{p['relevance_score']}/10] {p['title']} ({p['source']})")
            text_lines.append(f"  {p['summary']}")
            text_lines.append(f"  Why: {p['why_relevant']}")
            text_lines.append(f"  {p['url']}")
    if recommendations:
        text_lines.append("\n\nPROJECT RECOMMENDATIONS:")
        for r in recommendations:
            text_lines.append(f"\n  [{r['effort'].upper()}] {r['recommendation']}")
            text_lines.append(f"  Inspired by: {r['inspired_by']}")
            text_lines.append(f"  Impact: {r['impact']}")
    text_body = "\n".join(text_lines)

    # HTML body
    post_rows = ""
    for p in top_posts:
        sc = "#27ae60" if p["relevance_score"] >= 8 else "#f39c12" if p["relevance_score"] >= 6 else "#95a5a6"
        post_rows += f"""
        <div style="border-left:4px solid {sc};padding:12px 16px;margin:12px 0;background:#f8f9fa;border-radius:0 4px 4px 0">
          <div style="font-size:13px;color:{sc};font-weight:600;margin-bottom:4px">
            {p['relevance_score']}/10 — {p['source']}
          </div>
          <div style="font-weight:600;margin-bottom:6px">
            <a href="{p['url']}" style="color:#2c3e50;text-decoration:none">{p['title']}</a>
          </div>
          <div style="font-size:14px;color:#555;margin-bottom:4px">{p['summary']}</div>
          <div style="font-size:13px;color:#888">Why it matters: {p['why_relevant']}</div>
        </div>"""

    effort_colors = {"small": "#27ae60", "medium": "#f39c12", "large": "#e74c3c"}
    rec_rows = ""
    for r in recommendations:
        ec = effort_colors.get(r["effort"], "#95a5a6")
        rec_rows += f"""
        <div style="padding:12px 16px;margin:12px 0;background:#fff;border:1px solid #e0e0e0;border-radius:4px">
          <div style="display:inline-block;background:{ec};color:#fff;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;margin-bottom:6px">
            {r['effort'].upper()}
          </div>
          <div style="font-weight:600;margin:6px 0">{r['recommendation']}</div>
          <div style="font-size:13px;color:#888">Inspired by: {r['inspired_by']}</div>
          <div style="font-size:13px;color:#555;margin-top:4px">Impact: {r['impact']}</div>
        </div>"""

    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto">
  <div style="background:#4472C4;padding:20px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;color:#fff">AI Best Practices Digest</h2>
    <p style="margin:4px 0 0;color:#ccd9f0;font-size:14px">{project_name} — {week_label}</p>
  </div>
  <div style="background:#fff;padding:24px;border:1px solid #eee">
    <h3 style="color:#2c3e50;border-bottom:1px solid #eee;padding-bottom:8px">
      Top Posts ({len(top_posts)})
    </h3>
    {post_rows if post_rows else '<p style="color:#888">No highly relevant posts this week.</p>'}
    <h3 style="color:#2c3e50;border-bottom:1px solid #eee;padding-bottom:8px;margin-top:24px">
      Project Recommendations ({len(recommendations)})
    </h3>
    {rec_rows if rec_rows else '<p style="color:#888">No new recommendations this week.</p>'}
  </div>
  <div style="background:#f8f9fa;padding:12px 24px;border-radius:0 0 8px 8px;border:1px solid #eee;border-top:none">
    <p style="color:#888;font-size:12px;margin:0">
      Generated by ai-digest for {project_name}. Sources: {', '.join(set(p['source'] for p in top_posts)) or 'N/A'}.
    </p>
  </div>
</div>""".strip()

    return subject, html_body, text_body


def _send_email(subject: str, html_body: str, text_body: str,
                from_email: str, to_email: str) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", from_email)
    password = os.environ.get("SMTP_PASS", "")

    if not (user and password):
        log.warning("smtp_not_configured", has_user=bool(user), has_pass=bool(password))
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        log.info("digest_sent", to=to_email, subject=subject)
        return True
    except Exception as e:
        log.error("digest_send_failed", error=str(e))
        return False


KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "digest_knowledge"


def _save_digest_knowledge(analysis: dict, project_name: str, date_str: str):
    """Save digest analysis to knowledge base for long-term reference."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    top_posts = analysis.get("top_posts", [])
    recommendations = analysis.get("project_recommendations", [])

    if not top_posts and not recommendations:
        return

    filename = f"{date_str}_{project_name}.md"
    path = KNOWLEDGE_DIR / filename

    lines = [f"# Digest: {project_name} — {date_str}\n"]

    if top_posts:
        lines.append("## Top Posts\n")
        for p in top_posts:
            lines.append(f"- **{p.get('title', 'Untitled')}** ({p.get('source', '?')}) "
                         f"— relevance {p.get('relevance_score', '?')}/10")
            lines.append(f"  {p.get('summary', '')}")
            lines.append(f"  Why: {p.get('why_relevant', '')}\n")

    if recommendations:
        lines.append("## Recommendations\n")
        for r in recommendations:
            lines.append(f"- [{r.get('effort', '?').upper()}] {r.get('title') or r.get('recommendation', '')}")
            if r.get('title'):
                lines.append(f"  {r.get('recommendation', '')}")
            lines.append(f"  Inspired by: {r.get('inspired_by', '')}")
            lines.append(f"  Impact: {r.get('impact', '')}")
            if r.get('where_it_fits'):
                lines.append(f"  Where it fits: {r['where_it_fits']}")
            if r.get('first_step'):
                lines.append(f"  First step: {r['first_step']}")
            if r.get('risks'):
                lines.append(f"  Risks: {r['risks']}")
            lines.append("")

    path.write_text("\n".join(lines))
    log.info("digest_knowledge_saved", path=str(path), posts=len(top_posts),
             recommendations=len(recommendations))


def _build_issue_body(analysis: dict, project_name: str, date_str: str) -> str:
    """Build a self-contained GitHub issue body from a digest analysis."""
    top_posts = analysis.get("top_posts", [])
    recommendations = analysis.get("project_recommendations", [])

    lines = [
        f"## Source",
        f"`~/best-practices/data/digest_knowledge/{date_str}_{project_name}.md`",
        "",
        f"Auto-generated from the {date_str} weekly digest. The reference doc above has the raw analysis; this issue is the actionable view.",
        "",
    ]

    if top_posts:
        lines.append("## Top Posts to Read")
        lines.append("")
        for i, p in enumerate(top_posts, 1):
            url = p.get("url", "")
            title = p.get("title", "Untitled")
            source = p.get("source", "?")
            score = p.get("relevance_score", "?")
            lines.append(f"{i}. **[{title}]({url})** ({source}) — relevance {score}/10")
            if p.get("summary"):
                lines.append(f"   {p['summary']}")
            if p.get("why_relevant"):
                lines.append(f"   *Why it matters here:* {p['why_relevant']}")
            lines.append("")

    if recommendations:
        lines.append("## Ideas to Evaluate")
        lines.append("")
        for i, r in enumerate(recommendations, 1):
            effort = r.get("effort", "?").upper()
            title = r.get("title") or r.get("recommendation", "")[:80]
            lines.append(f"### {i}. {title}  [{effort}]")
            lines.append("")
            if r.get("recommendation"):
                lines.append(r["recommendation"])
                lines.append("")
            if r.get("where_it_fits"):
                lines.append(f"**Where it fits:** {r['where_it_fits']}")
                lines.append("")
            if r.get("first_step"):
                lines.append(f"**First step:** {r['first_step']}")
                lines.append("")
            if r.get("risks"):
                lines.append(f"**Risks / tradeoffs:** {r['risks']}")
                lines.append("")
            if r.get("impact"):
                lines.append(f"**Impact:** {r['impact']}")
                lines.append("")
            if r.get("inspired_by"):
                lines.append(f"*Inspired by:* {r['inspired_by']}")
                lines.append("")
            lines.append("---")
            lines.append("")

    lines.extend([
        "## Process",
        "",
        "Pick which idea to work on this week. None require all-or-nothing — start with the smallest first step listed.",
        "",
        "Comment progress / decisions on this issue. Close when satisfied; spawn follow-up issues for anything that warrants its own scope.",
        "",
        "*This issue was auto-generated by the weekly digest pipeline. The agent that opens it has full context to act — read it cold and start.*",
    ])

    return "\n".join(lines)


def _create_github_issue(analysis: dict, ctx: dict, project_name: str,
                          date_str: str) -> bool:
    """Create a GitHub issue in the configured target repo. Idempotent by title.

    Requires `gh` CLI authenticated locally with cross-repo access. Skips silently
    if `gh auth status` fails (e.g., when running in CI without a token).
    """
    import subprocess

    issue_cfg = ctx.get("github_issue", {})
    repo = issue_cfg.get("repo")
    if not repo:
        return False

    # Verify gh is authenticated before doing anything.
    try:
        auth_check = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=10
        )
        if auth_check.returncode != 0:
            log.info("issue_skipped_no_gh_auth", repo=repo,
                     hint="CI does not create issues; run scripts/run_weekly_digest.sh locally")
            return False
    except Exception as e:
        log.info("issue_skipped_gh_unavailable", repo=repo, error=str(e))
        return False

    top_posts = analysis.get("top_posts", [])
    recommendations = analysis.get("project_recommendations", [])
    if not top_posts and not recommendations:
        log.info("issue_skipped_empty_analysis", repo=repo)
        return False

    title_prefix = issue_cfg.get("title_prefix", "Weekly digest")
    title = f"{title_prefix} {date_str}: ideas to evaluate"
    labels = issue_cfg.get("labels", [])

    # Idempotency: skip if an issue with this exact title already exists.
    try:
        check = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "all",
             "--search", f'in:title "{title}"', "--json", "number,title"],
            capture_output=True, text=True, timeout=30,
        )
        if check.returncode == 0 and title in check.stdout:
            log.info("issue_already_exists", repo=repo, title=title)
            return True
    except Exception as e:
        log.warning("issue_existence_check_failed", repo=repo, error=str(e))

    body = _build_issue_body(analysis, project_name, date_str)

    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])

    # Retry once on a transient GitHub error. On 2026-09-04 this returned
    # "HTTP 504: Gateway Timeout" from the GraphQL API and the digest issue was
    # simply never filed — the caller discards this bool, so nothing counted the
    # loss and the run still reported that context as healthy.
    for attempt in (1, 2):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                url = result.stdout.strip()
                log.info("issue_created", repo=repo, url=url, title=title)
                return True
            stderr = result.stderr[:500]
            transient = any(code in stderr for code in ("HTTP 50", "timeout", "Timeout"))
            log.error("issue_create_failed", repo=repo, stderr=stderr,
                      attempt=attempt, will_retry=(transient and attempt == 1))
            if not (transient and attempt == 1):
                return False
        except Exception as e:
            log.error("issue_create_exception", repo=repo, error=str(e), attempt=attempt)
            if attempt == 2:
                return False
    return False


@click.command()
@click.option("--days", default=7, help="Look back N days for new posts")
@click.option("--dry-run", is_flag=True, help="Print to stdout instead of emailing")
@click.option("--context", "context_path", default=None,
              help="Path to context YAML (default: config/context.yaml)")
@click.option("--feeds", "feeds_path", default=None,
              help="Path to feeds YAML (default: config/feeds.yaml)")
@click.option("--backfill", is_flag=True,
              help="Fetch max history from all feeds and archive (no analysis)")
@click.option("--all-history", is_flag=True,
              help="Analyze all archived posts (capped at 8 weeks) instead of just this week")
def main(days: int, dry_run: bool, context_path: Optional[str],
         feeds_path: Optional[str], backfill: bool, all_history: bool):
    """Fetch AI/engineering posts, analyze relevance, and send digest."""
    ctx = _load_context(context_path)
    feeds = _load_feeds(feeds_path)
    project_name = ctx.get("project_name", "unknown")
    today = datetime.now().strftime("%Y-%m-%d")
    week_label = f"Week of {today}"

    if backfill:
        # Fetch everything available from all feeds and archive it
        log.info("backfill_start", feeds=len(feeds))
        _fetch_recent_posts(feeds, days=365)  # RSS feeds typically retain 3-6 months
        print("Backfill complete. Posts archived to data/feed_archive/posts.json")
        return

    log.info("digest_start", project=project_name, days=days, feeds=len(feeds))

    fetch_stats = None
    if all_history:
        # Use archived posts, capped at 8 weeks
        all_posts = fetch_all_archived_posts()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=56)).strftime("%Y-%m-%d")
        posts = [p for p in all_posts if p.get("published", "") >= cutoff]
        week_label = f"Full Review (last 8 weeks as of {today})"
        log.info("using_archive", total_archived=len(all_posts), within_window=len(posts))
    else:
        posts, fetch_stats = _fetch_feeds(feeds, days=days)

    # Distinguish "no news" from "no fetch". Both used to exit 0 having sent
    # nothing, so a total feed outage was indistinguishable from a quiet week
    # and run_weekly_digest.sh — which counts a context as failed via the exit
    # status — never reported it.
    if fetch_stats and fetch_stats["total"]:
        failed, total = len(fetch_stats["failed"]), fetch_stats["total"]
        if failed > total * FEED_FAILURE_THRESHOLD:
            sources = ", ".join(f["source"] for f in fetch_stats["failed"][:10])
            log.error("feed_fetch_majority_failed", failed=failed, total=total)
            print(f"Feed fetch failed for {failed}/{total} sources: {sources}",
                  file=sys.stderr)
            sys.exit(1)
        if not posts and fetch_stats["ok"] == 0:
            log.error("feed_fetch_total_failure", total=total)
            print(f"No posts and no feed fetched successfully ({total} configured).",
                  file=sys.stderr)
            sys.exit(1)

        # Informational only — a stale feed still fetches, so the run proceeds.
        stale = fetch_stats.get("stale") or []
        if stale:
            worst = ", ".join(f"{s['source']} ({s['days']}d)"
                              for s in sorted(stale, key=lambda s: -s["days"])[:5])
            print(f"{len(stale)} feed(s) stale >{FEED_STALE_DAYS}d — may be dead "
                  f"rather than quiet: {worst}", file=sys.stderr)

    # Inbox items ride along with whatever the feeds produced (and can rescue
    # an otherwise-quiet week from the early exit below).
    inbox_posts = _load_inbox_posts(_load_archive())
    seen_links = {p["link"] for p in posts}
    posts.extend(p for p in inbox_posts if p["link"] not in seen_links)

    if not posts:
        # Feeds fetched fine, nothing new in the window — a genuinely quiet week.
        print("No new posts found.")
        return

    # Verdict feedback loop: pull evaluation verdicts from newly closed digest
    # issues into the per-project ledger, then inject the ledger into the
    # prompt so rejected ideas are not re-proposed. Collection needs local gh
    # auth (skipped in the Actions fallback); injection only needs the
    # committed ledger, so it works everywhere. Never blocks the run.
    from digest.verdict_feedback import collect_verdicts, render_verdict_block
    if not dry_run:
        collect_verdicts(ctx)

    log.info("analyzing_posts", count=len(posts))
    context_prompt = _build_context_prompt(ctx) + render_verdict_block(project_name)
    analysis = _analyze_posts(posts, context_prompt, project_name)
    if not analysis:
        # Must be non-zero: run_weekly_digest.sh counts a failed context via the
        # exit status and alerts on it. A bare `return` here exits 0, which is why
        # the 2026-07-03 wealth-mgmt json_parse_failed went out silently.
        print("Failed to analyze posts.", file=sys.stderr)
        sys.exit(1)

    top_count = len(analysis.get("top_posts", []))
    rec_count = len(analysis.get("project_recommendations", []))
    log.info("analysis_complete", top_posts=top_count, recommendations=rec_count)

    # Persist analysis to knowledge base
    _save_digest_knowledge(analysis, project_name, today)

    subject, html_body, text_body = _build_email(analysis, week_label, project_name)

    if dry_run:
        print(f"\n{'='*60}")
        print(f"Subject: {subject}")
        print(f"{'='*60}")
        print(text_body)
        print(f"{'='*60}")
        return

    email_cfg = ctx.get("email", {})
    from_email = email_cfg.get("from", os.environ.get("ALERT_EMAIL", ""))
    to_email = email_cfg.get("to", os.environ.get("ALERT_EMAIL", ""))

    if not from_email or not to_email:
        print("No email configured. Use --dry-run or set email in context.yaml")
        return

    success = _send_email(subject, html_body, text_body, from_email, to_email)
    if success:
        print(f"Digest sent: {subject}")
    else:
        print("Failed to send. Check logs.")

    # Create GitHub issue in target repo (if configured)
    if ctx.get("github_issue", {}).get("repo"):
        _create_github_issue(analysis, ctx, project_name, today)


if __name__ == "__main__":
    main()
