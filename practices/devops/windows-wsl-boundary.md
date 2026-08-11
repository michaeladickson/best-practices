# The Windows / WSL Boundary

Every repo in this stack is edited on Windows and executed under WSL. The boundary
is quiet until it isn't, and its failures share a shape: **the code is correct, the
bytes on disk are not, and every tool you would normally trust reports success.**

## Line endings: pin them in `.gitattributes`, per file type

Git for Windows ships `core.autocrlf=true` at *system* scope (`/etc/gitconfig`), so
it applies even when local and global are unset. Blobs are stored LF and the working
tree is checked out CRLF.

For a script WSL executes, a CRLF shebang is fatal. The kernel looks for an
interpreter literally named `/bin/bash\r`:

```
bash: /mnt/c/.../run_weekly.sh: cannot execute: required file not found
exit 127
```

Exit 127 means "command not found", which sends you hunting for a missing binary
rather than a carriage return.

**Pin what the other side executes:**

```gitattributes
*.sh  text eol=lf     # WSL bash
*.py  text eol=lf     # anything with a shebang, or that may gain one
*.yml text eol=lf     # CI runners
*.sql text eol=lf     # psql, and anything regex-processed across the boundary

*.ps1 text eol=crlf   # Windows-native — Task Scheduler, wscript.exe
*.vbs text eol=crlf
*.bat text eol=crlf
*.cmd text eol=crlf
```

### The part that makes it expensive: git cannot see it

`.gitattributes` applies **at checkout**. A file checked out *before* the rule
existed keeps its CRLF indefinitely, and `git status` stays clean forever — git
normalizes on read, so the corruption exists only in the working tree. It is
invisible to code review, to CI, and to `git diff`.

Adding the rule does not fix files already on disk. Refresh them:

```bash
git rm --cached -r . && git reset --hard   # clean tree only; re-checkouts with attributes applied
```

Verify by bytes, not by eye — `tr -cd '\r' < file | wc -c` should be 0 for LF files.

### Do not blanket-pin

Pin what the other side *executes*, not everything. Where writers are mixed — an
editor writing CRLF, rsync/WSL writing LF — a broad `eol=` pin only relocates
cosmetic `git status` churn without preventing a real failure. crumbl-ops
deliberately uses `* text=auto` for the index plus targeted pins, and documents the
refusal in its own `.gitattributes`. "Make every repo's file identical" is the wrong
generalization.

## Verifying across the boundary: the tools lie in specific ways

- **Don't invoke a WSL path from Git Bash.** MSYS rewrites a bare `/mnt/...`
  argument into `C:/Program Files/Git/mnt/...`, which the inner shell splits at the
  space — producing `C:/Program: No such file or directory` and a *fake* failure
  that mimics the real one. Dispatch from PowerShell or `Start-ScheduledTask`.
- **A healthy Task Scheduler entry is not evidence.** `State=Ready` and
  `NumberOfMissedRuns=0` describe the *scheduler*, not the payload. Read
  `LastTaskResult` (0 = success); a task can fire on time and exit 127 every week
  while the UI looks green.
- **`gcloud` working proves nothing about Python.** The client libraries use
  Application Default Credentials, a separate path. Verify from the venv.
- **Windows and WSL have different interpreters.** `python` on the Windows PATH is
  not the WSL venv; a package present in one is absent in the other.

## The rule underneath

A correct fix that lives only in a code comment does not propagate. This lesson
existed as a comment in two repos' `.gitattributes` and was missing from the third —
where a weekly scheduled job then returned 127 for two weeks with a clean
`git status` the entire time. Comments explain *this* file to whoever opens it;
that is a different job from telling a new repo what to adopt.

## Sources

- 2026-08-10/11, wealth-mgmt: `WM-WeeklyDigest` dead since registration — CRLF
  shebang in `scripts/run_weekly.sh` (git held LF), diagnosed only by executing it.
- 2026-05-10, crumbl-ops: CRLF made bash read `set -euo pipefail\r` and silently
  disable strict mode.
- crumbl-ops `.gitattributes` (2026-05-29, corrected 2026-08-02) — the measured
  argument against blanket `eol=` pinning.

## Where Used

- **wealth-mgmt**: `.gitattributes` pins `*.sh`/`*.py` LF, `*.ps1`/`*.vbs` CRLF
- **crumbl-ops**: `* text=auto` + targeted pins for `*.sh`, `*.yml`, `*.sql`; explicit
  refusal to pin broadly
- **best-practices**: `* text=auto eol=lf` + explicit `*.sh`/`*.bash`/`*.py`
- **command-center**: origin of the fix these mirror
