#!/bin/bash
# scripts/run_weekly_digest.sh
#
# Local weekly digest runner. Registered with Windows Task Scheduler as
# CC-WeeklyDigest (Friday 6pm ET). Runs each context in CONTEXTS, sends emails,
# creates GH issues in target repos using local gh auth, then commits +
# pushes the digest knowledge files back to best-practices.
#
# Secrets are pulled from GCP Secret Manager — no .env needed.
# Required GCP secrets in project hybrid-elysium-471814-p2:
#   - gemini-api-key
#   - smtp-password
# Local prerequisites:
#   - gh CLI authenticated (`gh auth status` returns OK)
#   - Windows-side gcloud has the service account credentialed
#     (`gcloud auth list` shows crumbl-ops-dev@...; key-based, immune to reauth)
#   - python3 with digest/requirements.txt installed
#   - git push access to origin

set -e
set -o pipefail  # so the gcloud failure in `gcloud_w | tr` actually propagates
cd "$(dirname "$0")/.."

# Fast-forward before doing any work, so this run's commits are built on a
# current base. Sessions push to origin/main from worktrees, which leaves THIS
# checkout behind without touching its working tree — nothing here looks wrong,
# and the tell only appears at the end when `git push origin main` is rejected
# as non-fast-forward. That push failure is a warning, not a fatal, so the
# knowledge files and telemetry would just silently not land (observed
# 2026-09-13: main checkout 3 commits behind after a session pushed).
#
# Warn rather than exit: the digests are the deliverable and still email fine
# from a stale base. --ff-only so a genuinely diverged checkout is reported
# instead of being merged blind.
if ! git pull --ff-only origin main; then
  echo "WARNING: could not fast-forward to origin/main — this checkout may be" >&2
  echo "         behind or diverged, and the commits below may fail to push." >&2
  echo "         Current: $(git rev-parse --short HEAD)  origin/main: $(git rev-parse --short origin/main 2>/dev/null || echo unknown)" >&2
fi

GCP_PROJECT="hybrid-elysium-471814-p2"

# Unattended secret fetch uses a key-based service account, NOT the interactive
# user account. The Workspace reauth policy periodically invalidates the user
# account's creds for non-interactive use (it broke this job repeatedly); the
# SA key is immune. The SA is pre-credentialed in gcloud and has
# secretmanager.secretAccessor on both secrets.
#
# DEDICATED SA -- DO NOT point this at a shared SA. cc-digest@ is private to this
# digest and scoped to secretAccessor on ONLY gemini-api-key + smtp-password.
# It was previously crumbl-ops-dev@, but that SA is shared with crumbl-ops; a
# crumbl-ops security sweep (their #665) deleted its key on 2026-06-05 during a
# keyless-ADC migration, silently breaking this digest (command-center #216).
# A private, minimal-scope SA decouples the two repos so neither breaks the other.
# See command-center decisions/2026-06-15-digest-service-account.md.
SA_ACCOUNT="cc-digest@hybrid-elysium-471814-p2.iam.gserviceaccount.com"

# Use Windows-side gcloud (via cmd.exe) instead of WSL gcloud. WSL gcloud auth
# silently expires after a few weeks of inactivity; Windows-side stays fresh
# through daily interactive use. The cmd.exe wrapper lets us call the
# Windows-installed gcloud from this WSL shell.
#
# stderr is CAPTURED, not discarded. It used to go to /dev/null, which meant
# every failure mode collapsed into "cannot mint a token (key missing/revoked)"
# — a confidently wrong diagnosis. On 2026-07-31 that produced an urgent-labelled
# issue naming a cause that did not reproduce: the SA minted a token fine the
# next morning through this exact path. Without the real gcloud error there was
# nothing to diagnose from. GCLOUD_ERR holds the last call's stderr.
#
# stderr goes to a FILE, not a shell variable. Every caller here is either
# `X=$(gcloud_w ...)` or `gcloud_w ... | grep` — both run the function in a
# subshell, so a variable assigned inside it is discarded before anyone can read
# it. A file survives. (This bit the first version of this fix.)
GCLOUD_ERR_FILE=$(mktemp)
trap 'rm -f "$GCLOUD_ERR_FILE"' EXIT
gcloud_w() {
  local out rc=0
  out=$(cmd.exe /c "gcloud $*" 2>"$GCLOUD_ERR_FILE" | tr -d '\r') || rc=$?
  printf '%s' "$out"
  return "$rc"
}

# Render the last gcloud call's stderr for an alert body, or say plainly that
# there was none. Drops cmd.exe's UNC-path preamble, which it emits on every
# call from WSL and which says nothing about the failure.
gcloud_err_block() {
  local err
  err=$(tr -d '\r' <"$GCLOUD_ERR_FILE" 2>/dev/null \
        | grep -v -e '^.\\\\wsl' -e '^CMD.EXE was started' -e '^UNC paths are not supported' \
        | tail -n 12)
  if [ -n "$err" ]; then
    printf '\n**gcloud stderr:**\n```\n%s\n```\n' "$err"
  else
    printf '\n_gcloud wrote nothing to stderr — the call produced no output and no error. Re-run before assuming a cause._\n'
  fi
}

ALERT_REPO="michaeladickson/command-center"
ALERT_TITLE="⚠️ Weekly digest blocked — service-account secret fetch failed"

# Create a deduplicated GH issue and abort. Used when the run can't proceed
# (e.g. the service account can't mint a token or read a secret). gh auth is
# verified before any caller, so this channel works even when the gcloud
# channel is dead.
alert_and_exit() {
  local reason="$1"
  echo "ERROR: $reason" >&2
  local existing
  existing=$(gh issue list --repo "$ALERT_REPO" --state open --search "$ALERT_TITLE in:title" --json number --jq '.[0].number // empty' 2>/dev/null || true)
  if [ -n "$existing" ]; then
    echo "Alert issue already open: $ALERT_REPO#$existing (not duplicating)." >&2
  else
    local body
    body="Weekly digest run aborted at $(date -Is).

**Reason:** $reason
$(gcloud_err_block)
**Read the stderr above before assuming a cause.** Secrets are fetched via
service account \`$SA_ACCOUNT\` (key-based, normally immune to user reauth).
Candidate causes, only if the stderr supports one:
1. **SA credential missing/revoked** — check \`gcloud auth list\` still shows the SA; re-activate its key if it's gone.
2. **SA lost access** — confirm it still has \`secretmanager.secretAccessor\` on gemini-api-key + smtp-password in project $GCP_PROJECT.
3. **Transient / no stderr at all** — re-run first. A run has aborted here once (2026-07-31) with the SA perfectly healthy.

**Re-run (the token mint is worth testing on its own first):**
\`\`\`
gcloud --account=$SA_ACCOUNT auth print-access-token | wc -c
\`\`\`
\`\`\`
bash /mnt/c/Users/micha/best-practices/scripts/run_weekly_digest.sh
\`\`\`"
    if gh issue create --repo "$ALERT_REPO" --title "$ALERT_TITLE" --label priority/urgent --body "$body" >/dev/null 2>&1 \
       || gh issue create --repo "$ALERT_REPO" --title "$ALERT_TITLE" --body "$body" >/dev/null 2>&1; then
      echo "Created alert issue in $ALERT_REPO." >&2
    else
      echo "WARNING: could not create alert issue (gh error)." >&2
    fi
  fi
  exit 1
}

PARTIAL_TITLE="Weekly digest: partial failure"

# Record a partial failure in one open issue: comment on it if it is already
# open (a recurring failure stays one thread), else create it. Returns non-zero
# only when gh could not write either, so the caller can fall back to exit 1.
report_partial_failure() {
  local body="$1" existing
  existing=$(gh issue list --repo "$ALERT_REPO" --state open --search "\"$PARTIAL_TITLE\" in:title" --json number,title \
               --jq ".[] | select(.title == \"$PARTIAL_TITLE\") | .number" 2>/dev/null | head -n1 || true)
  if [ -n "$existing" ]; then
    gh issue comment "$existing" --repo "$ALERT_REPO" --body "$body" >/dev/null 2>&1 \
      && echo "Commented on $ALERT_REPO#$existing ($PARTIAL_TITLE)." && return 0
  else
    gh issue create --repo "$ALERT_REPO" --title "$PARTIAL_TITLE" --body "$body" >/dev/null 2>&1 \
      && echo "Created $ALERT_REPO issue: $PARTIAL_TITLE." && return 0
  fi
  echo "WARNING: could not record the partial failure in $ALERT_REPO (gh error)." >&2
  return 1
}

# Verify the alert channel FIRST — if gh is dead too, fail quietly (no channel
# to alert through). Everything below routes failures through alert_and_exit.
echo "=== Verifying gh auth (alert channel) ==="
gh auth status >/dev/null 2>&1 || {
  echo "ERROR: gh CLI not authenticated. Run 'gh auth login' first." >&2
  exit 1
}

# Pre-flight: confirm the service account can mint a token before kicking off
# three doomed digests. The token is held in a variable and never printed.
#
# NOT piped into grep: a pipe puts gcloud_w in a subshell and throws away the
# GCLOUD_ERR it just captured, which is the whole point of capturing it.
echo "=== Pre-flight: service-account access token ==="
_PREFLIGHT_TOKEN=""
_PREFLIGHT_RC=0
_PREFLIGHT_TOKEN=$(gcloud_w "--account=$SA_ACCOUNT auth print-access-token") || _PREFLIGHT_RC=$?
if [ "$_PREFLIGHT_RC" -ne 0 ] || [ -z "$_PREFLIGHT_TOKEN" ]; then
  alert_and_exit "Service account $SA_ACCOUNT returned no access token (gcloud exit $_PREFLIGHT_RC). Secret Manager access would fail, so all 3 digests would error out."
fi
unset _PREFLIGHT_TOKEN

echo "=== Fetching secrets from GCP Secret Manager (service account) ==="
GEMINI_API_KEY=$(gcloud_w "--account=$SA_ACCOUNT secrets versions access latest --secret=gemini-api-key --project=$GCP_PROJECT") \
  || alert_and_exit "Failed to fetch gemini-api-key from Secret Manager via $SA_ACCOUNT."
if [ -z "$GEMINI_API_KEY" ]; then
  alert_and_exit "gemini-api-key fetch via $SA_ACCOUNT returned empty (check the SA's secretAccessor grant)."
fi
SMTP_PASS=$(gcloud_w "--account=$SA_ACCOUNT secrets versions access latest --secret=smtp-password --project=$GCP_PROJECT") \
  || alert_and_exit "Failed to fetch smtp-password from Secret Manager via $SA_ACCOUNT."
if [ -z "$SMTP_PASS" ]; then
  alert_and_exit "smtp-password fetch via $SA_ACCOUNT returned empty (check the SA's secretAccessor grant)."
fi
export GEMINI_API_KEY SMTP_PASS
export SMTP_USER="michael@bluegrasscookies.com"

# command-center was retired 2026-09-21: its weekly idea issues closed with no
# action in most weeks, so the run was manufacturing a triage chore.
CONTEXTS="crumbl-ops wealth-mgmt"

FAILED=0
DIGESTS_FAILED=0
DIGESTS_OK=0
PRACTICE_FAILED=0
PRACTICE_COMMITTED=0
FAILED_CONTEXTS=""
for CTX in $CONTEXTS; do
  echo ""
  echo "=== Running $CTX digest ==="
  if ! python3 -m digest --context "digest/config/context-${CTX}.yaml" --days 7; then
    echo "WARNING: $CTX digest failed" >&2
    FAILED=$((FAILED + 1))
    DIGESTS_FAILED=$((DIGESTS_FAILED + 1))
    FAILED_CONTEXTS="$FAILED_CONTEXTS $CTX"
    continue
  fi
  DIGESTS_OK=$((DIGESTS_OK + 1))

  # Commit each context's knowledge file as soon as it lands, rather than once
  # at the end. This run is a long serial chain (3 digests + a 5-doc practice
  # update); when it was killed mid-run on 2026-07-17 the completed crumbl-ops
  # knowledge file was left uncommitted because the batch commit never ran.
  git add data/digest_knowledge/ data/digest_feedback/
  if ! git diff --cached --quiet; then
    git commit -q -m "Weekly digest: ${CTX} knowledge file [automated]"
    echo "Committed $CTX knowledge file"
  fi
done

# Push the digest commits before the practice update, so a hang there can't
# strand them locally.
git push -q origin main || echo "WARNING: push of digest knowledge failed" >&2

echo ""
echo "=== Updating living practice docs from this week's articles ==="
# Auto-edits every doc listed in digest/config/practice-docs.yaml from the same
# archived articles. Dedup ledger + structural validation guard the writes.
# Exits non-zero when a doc is BLOCKED (validation-rejected, at the size cap, or
# errored). A blocked doc's candidates are NOT retried next week: the ledger only
# records successes, and the --days 7 window slides past this week's articles by
# the next Friday run — so they are silently lost unless the updater is re-run
# before then (2026-08-28: the llm-evaluation block was recovered only by a
# same-week manual re-run). It still exits 0 for a normal no-new-articles week.
# Any partial edits it DID write are committed below regardless, so failing here
# never strands work.
if ! python3 -m digest.practice_updater --days 7; then
  echo "WARNING: practice-doc update reported blocked doc(s) — see the BLOCKED list above" >&2
  FAILED=$((FAILED + 1))
  PRACTICE_FAILED=1
fi

echo ""
echo "=== Committing practice-doc updates ==="
# Stage every doc the updater is configured to touch, read from the same config
# it uses. This list was previously hardcoded to 2 of the 5 configured docs, so
# edits to the other 3 were made and silently never committed — while the
# incorporated.json dedup ledger WAS committed, which would make the lost
# content unregenerable. Deriving from config keeps the two in sync.
PRACTICE_DOCS=$(python3 -c "
import sys, yaml
from pathlib import Path
with open('digest/config/practice-docs.yaml') as f:
    cfg = yaml.safe_load(f) or {}
for d in cfg.get('docs', []):
    p = d.get('path')
    if not p:
        continue
    # Skip paths that don't exist rather than aborting the run on 'git add' —
    # a stale config entry shouldn't cost us the commit of the real edits.
    if Path(p).exists():
        print(p)
    else:
        print(f'WARNING: configured practice doc missing: {p}', file=sys.stderr)
")
if [ -z "$PRACTICE_DOCS" ]; then
  echo "WARNING: no practice-doc paths read from config; nothing staged" >&2
  FAILED=$((FAILED + 1))
fi
# shellcheck disable=SC2086
git add -- $PRACTICE_DOCS data/practice_updates/
if git diff --cached --quiet; then
  echo "No practice-doc updates to commit"
else
  git commit -m "Weekly practice update: living docs refreshed from digest articles [automated]"
  git push origin main
  PRACTICE_COMMITTED=1
  echo "Committed and pushed practice-doc updates"
fi

# Retire consumed inbox items only after ALL contexts have run (the loader in
# ai_digest.py is non-destructive so every digest sees them). Only on full
# success — a failed context re-reads them next attempt; the archive dedups.
if [ "$DIGESTS_FAILED" -eq 0 ] && ls data/digest_inbox/*.md >/dev/null 2>&1; then
  mkdir -p data/digest_inbox/processed
  mv data/digest_inbox/*.md data/digest_inbox/processed/
  echo "Inbox items moved to processed/"
fi

echo ""
echo "=== Feed instrumentation (yield report, citation discovery, heartbeats, model pricing) ==="
# All of these are best-effort: a failure warns but never fails the run — the
# digests and practice updates above are the deliverables, this is telemetry.
# citation_discovery files feed-candidate issues via local gh auth;
# check_heartbeats files an issue only when a scheduled job's state is stale.
python3 -m digest.feed_report || echo "WARNING: feed report failed" >&2
python3 -m digest.citation_discovery || echo "WARNING: citation discovery failed" >&2
python3 scripts/check_heartbeats.py || echo "WARNING: stale heartbeat(s) detected — issue filed" >&2
# Spend tripwires (report is gitignored — spend data stays out of this public
# repo; alerts file into command-center). Needs WSL gh with the "user" scope.
python3 scripts/check_gh_usage.py || echo "WARNING: GH usage tripwire fired or check failed — see above" >&2
# Standing price check on the model watchlist. Files an issue only when a
# tracked model's rate moves >=5% or leaves the feed; otherwise it just
# refreshes data/model_pricing.md and the weekly commit carries the diff.
python3 -m digest.model_pricing || echo "WARNING: model pricing check failed" >&2

git add data/feed_report.md data/feed_candidates.json data/model_pricing.md data/model_pricing.json 2>/dev/null
if ! git diff --cached --quiet; then
  git commit -q -m "Weekly telemetry: feed report + citation ledger + model pricing [automated]"
  git push -q origin main || echo "WARNING: push of telemetry failed" >&2
fi

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "WARNING: $FAILED step(s) failed."
  if [ "$DIGESTS_FAILED" -gt 0 ]; then
    echo "  $DIGESTS_FAILED context digest(s) failed. Re-run individually:"
    echo "    python3 -m digest --context digest/config/context-<name>.yaml --days 7"
  fi
  if [ "$PRACTICE_FAILED" -gt 0 ]; then
    echo "  Practice-doc update had blocked doc(s). Their candidates are LOST once"
    echo "  the --days 7 window slides past them (next Friday) — NOT retried. Fix"
    echo "  the blocked doc (e.g. consolidate it) and re-run BEFORE then, in the"
    echo "  main checkout with GEMINI_API_KEY from Secret Manager (SA cc-digest@):"
    echo "    python3 -m digest.practice_updater --days 7"
  fi

  # Exit 1 only when the run delivered NOTHING. A partial failure used to exit 1
  # too, so the task read FAILED in 3 of 4 weeks (8/28-9/18) while the emails
  # went out, and the red stopped meaning anything. A partial failure still needs
  # a human (a blocked doc's candidates are lost by next Friday), so it is carried
  # by an open issue instead of the task's exit code. If that issue cannot be
  # filed, fall back to exit 1: a silent partial failure is the worst outcome.
  if [ "$DIGESTS_OK" -eq 0 ] && [ "$PRACTICE_COMMITTED" -eq 0 ]; then
    echo "ERROR: nothing was delivered this run." >&2
    exit 1
  fi
  PARTIAL_BODY="Weekly digest run $(date -Is) delivered partially.

- Context digests sent: $DIGESTS_OK of $(echo $CONTEXTS | wc -w)${FAILED_CONTEXTS:+ (failed:$FAILED_CONTEXTS)}
- Practice-doc update: $([ "$PRACTICE_FAILED" -eq 1 ] && echo 'BLOCKED doc(s), candidates are lost at the next Friday run unless re-run before then' || echo 'ok')

Log: \`best-practices/logs/weekly_digest.log\` (search this run's date).
Re-run a context: \`python3 -m digest --context digest/config/context-<name>.yaml --days 7\`
Re-run the practice update after fixing the blocked doc: \`python3 -m digest.practice_updater --days 7\`
Close this issue once handled; the next partial failure opens a new one."
  if ! report_partial_failure "$PARTIAL_BODY"; then
    echo "ERROR: partial failure could not be recorded in an issue; exiting 1 so it is not silent." >&2
    exit 1
  fi
  echo ""
  echo "=== Weekly digest complete, with the partial failure above (issue filed) ==="
  exit 0
fi

echo ""
echo "=== Weekly digest complete ==="
