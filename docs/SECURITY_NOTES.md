# Security notes

## Committed token file (`.tmp_token.txt`)

`.tmp_token.txt` was committed to git history. It has been removed from the index and is now git-ignored
(`.gitignore` also ignores `*.token`). Removing it from the index does **not** remove it from history,
and anyone with a clone can still read it.

### 1. Rotate the token first

Treat the token as compromised. Revoke it at its issuer and issue a replacement before anything else.
Do not reuse the old value.

### 2. Purge the file from history (run yourself)

This rewrites history and changes every commit hash. Coordinate with anyone who has a clone, and
make a backup first (`git clone --mirror <repo> backup.git`).

```bash
pip install git-filter-repo
git filter-repo --invert-paths --path .tmp_token.txt --force
```

Then force-push every branch and tag that contained the file:

```bash
git push origin --force --all
git push origin --force --tags
```

Afterwards, every collaborator must re-clone or hard-reset to the rewritten branches.
GitHub may keep cached views of old commits for a while; contact GitHub Support to purge them if the
token was sensitive enough to warrant it.

### 3. Verify

```bash
git log --all --oneline -- .tmp_token.txt   # should print nothing
git ls-files | grep -c tmp_token             # should print 0
```

## Other secrets

- `backend/.env` and `frontend/.env.local` are git-ignored. Never commit real values.
- `backend/.env.example` lists every variable with placeholder values only.
- The default `SECRET_KEY` in `backend/app/core/config.py` is for local development. Set a real one in production.
