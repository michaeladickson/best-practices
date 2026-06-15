#!/bin/bash
# scripts/run_weekly_digest.sh
#
# Local weekly digest runner. Registered with Windows Task Scheduler as
# CC-WeeklyDigest (Sunday 6pm ET). Runs all three contexts, sends emails,
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
gcloud_w() {
  cmd.exe /c "gcloud $*" 2>/dev/null | tr -d '\r'
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

Secrets are fetched via service account \`$SA_ACCOUNT\` (key-based, normally immune to user reauth), so this usually means:
1. **SA credential missing/revoked** — check \`gcloud auth list\` still shows the SA; re-activate its key if it's gone.
2. **SA lost access** — confirm it still has \`secretmanager.secretAccessor\` on gemini-api-key + smtp-password in project $GCP_PROJECT.

**Then re-run:**
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

# Verify the alert channel FIRST — if gh is dead too, fail quietly (no channel
# to alert through). Everything below routes failures through alert_and_exit.
echo "=== Verifying gh auth (alert channel) ==="
gh auth status >/dev/null 2>&1 || {
  echo "ERROR: gh CLI not authenticated. Run 'gh auth login' first." >&2
  exit 1
}

# Pre-flight: confirm the service account can mint a token before kicking off
# three doomed digests. Token is consumed by grep and never printed.
echo "=== Pre-flight: service-account access token ==="
if ! gcloud_w "--account=$SA_ACCOUNT auth print-access-token" | grep -q .; then
  alert_and_exit "Service account $SA_ACCOUNT cannot mint an access token (key missing/revoked, or removed from the gcloud credential store). Secret Manager access would fail, so all 3 digests would error out."
fi

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

FAILED=0
for CTX in crumbl-ops command-center wealth-mgmt; do
  echo ""
  echo "=== Running $CTX digest ==="
  if ! python3 -m digest --context "digest/config/context-${CTX}.yaml" --days 7; then
    echo "WARNING: $CTX digest failed" >&2
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "=== Updating living practice docs from this week's articles ==="
# Auto-edits practices/claude-code/{context-memory-management,code-review-and-ai-slop}.md
# from the same archived articles. Dedup ledger + structural validation guard the writes.
if ! python3 -m digest.practice_updater --days 7; then
  echo "WARNING: practice-doc update failed" >&2
  FAILED=$((FAILED + 1))
fi

echo ""
echo "=== Committing knowledge files ==="
git add data/digest_knowledge/
if git diff --cached --quiet; then
  echo "No new digest knowledge to commit"
else
  COUNT=$(git diff --cached --name-only | wc -l)
  git commit -m "Weekly digest: ${COUNT} knowledge files updated [automated]"
  git push origin main
  echo "Committed and pushed $COUNT files"
fi

echo ""
echo "=== Committing practice-doc updates ==="
git add practices/claude-code/context-memory-management.md \
        practices/claude-code/code-review-and-ai-slop.md \
        data/practice_updates/
if git diff --cached --quiet; then
  echo "No practice-doc updates to commit"
else
  git commit -m "Weekly practice update: living docs refreshed from digest articles [automated]"
  git push origin main
  echo "Committed and pushed practice-doc updates"
fi

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "WARNING: $FAILED digest(s) failed. Re-run individually:"
  echo "  python3 -m digest --context digest/config/context-<name>.yaml --days 7"
  exit 1
fi

echo ""
echo "=== Weekly digest complete ==="
