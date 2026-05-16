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
#   - Windows-side gcloud authenticated (`gcloud.exe auth list` shows active account)
#   - python3 with digest/requirements.txt installed
#   - git push access to origin

set -e
cd "$(dirname "$0")/.."

GCP_PROJECT="hybrid-elysium-471814-p2"

# Use Windows-side gcloud (via cmd.exe) instead of WSL gcloud. WSL gcloud auth
# silently expires after a few weeks of inactivity; Windows-side stays fresh
# through daily interactive use. The cmd.exe wrapper lets us call the
# Windows-installed gcloud from this WSL shell.
gcloud_w() {
  cmd.exe /c "gcloud $*" 2>/dev/null | tr -d '\r'
}

echo "=== Fetching secrets from GCP Secret Manager ==="
GEMINI_API_KEY=$(gcloud_w "secrets versions access latest --secret=gemini-api-key --project=$GCP_PROJECT") || {
  echo "ERROR: failed to fetch gemini-api-key from Secret Manager." >&2
  echo "Add it via: echo -n '<key>' | gcloud secrets create gemini-api-key --data-file=- --project=$GCP_PROJECT" >&2
  exit 1
}
SMTP_PASS=$(gcloud_w "secrets versions access latest --secret=smtp-password --project=$GCP_PROJECT") || {
  echo "ERROR: failed to fetch smtp-password from Secret Manager." >&2
  exit 1
}
export GEMINI_API_KEY SMTP_PASS
export SMTP_USER="michael@bluegrasscookies.com"

echo "=== Verifying gh auth ==="
gh auth status >/dev/null || {
  echo "ERROR: gh CLI not authenticated. Run 'gh auth login' first." >&2
  exit 1
}

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

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "WARNING: $FAILED digest(s) failed. Re-run individually:"
  echo "  python3 -m digest --context digest/config/context-<name>.yaml --days 7"
  exit 1
fi

echo ""
echo "=== Weekly digest complete ==="
