#!/usr/bin/env bash
# Prove the tracked vendored patch reproduces the private fix on a pristine base,
# in a throwaway clone OUTSIDE the repo, then compare bytes with the live tree.
set -u

to_msys() {
  # Fold every path form this script can be handed into one comparable form:
  # MSYS-style, all lowercase, forward slashes, no doubled separators.
  # C:\Users\X, C:/Users/X and /c/Users/X all become /c/users/x.
  local p
  p="${1//\\//}"
  p=$(printf '%s' "$p" | tr 'A-Z' 'a-z' | sed 's#/\+#/#g')
  case "$p" in
    # `${p#*:}` strips through the first colon; `${p#:*}` would strip a prefix
    # that *starts* with a colon and silently match nothing here.
    [a-z]:/*) p="/${p%%:*}${p#*:}" ;;
  esac
  printf '%s\n' "$p"
}

canon() {
  # Resolve to one canonical form. The comparison this feeds is a literal
  # `case` match, so a single unrecognized input form silently defeats the
  # guard — that is how rm -rf once reached the live repository. Walk up to the
  # first existing ancestor (cd + pwd -P, already MSYS form), then re-attach the
  # nonexistent tail lexically, since the target usually does not exist yet.
  local p rest=""
  p=$(to_msys "$1")
  [ -n "$p" ] || return 0
  case "$p" in /*) ;; *) p=$(to_msys "$PWD/$p") ;; esac
  while :; do
    if [ -d "$p" ]; then
      p=$(cd "$p" && pwd -P)
      break
    fi
    case "$p" in
      /) printf '%s\n' "/$rest"; return ;;
    esac
    rest="/$(basename "$p")$rest"
    p=$(dirname "$p")
  done
  printf '%s\n' "$(to_msys "$p")$rest"
}

refuse() { echo "REFUSING: $1"; exit 1; }

REPO="${AE_KV_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENDOR="$REPO/external/rife"
PATCH="$REPO/docs/vendor/external-rife-audio-fallback-20260814.patch"
FIXED_OID="a1ad751a1849bfe851f8c53dd4b4115a2c0ec7e2"

# `${VAR:-default}` treats an empty value as unset, so an explicitly empty
# AE_KV_AMTEST_CLONE would silently fall back instead of being rejected.
if [ -n "${AE_KV_AMTEST_CLONE+set}" ]; then
  [ -n "$AE_KV_AMTEST_CLONE" ] || refuse "AE_KV_AMTEST_CLONE set but empty"
  CLONE="$AE_KV_AMTEST_CLONE"
else
  CLONE="$(dirname "$REPO")/ae-kv-amtest-$(date +%Y%m%d)"
fi

# This script does `rm -rf "$CLONE"`. Refuse any target that is not a disposable
# directory clear of the repository, so a bad AE_KV_AMTEST_CLONE cannot erase work.
C_REPO=$(canon "$REPO")
C_CLONE=$(canon "$CLONE")
C_HOME=$(canon "$HOME")
[ -n "$C_CLONE" ]     || refuse "empty clone target"
[ -n "$C_REPO" ]      || refuse "empty repository path"
[ "$C_CLONE" != "/" ] || refuse "clone target is filesystem root"
case "$C_CLONE" in
  /[a-z]|/[a-z]:) refuse "clone target is a drive root ($CLONE)" ;;
esac
case "$C_CLONE" in
  */.|*/..) refuse "clone target ends in . or .. ($CLONE)" ;;
esac
[ "$C_CLONE" != "$C_HOME" ] || refuse "clone target is \$HOME ($CLONE)"
case "$C_HOME" in
  "$C_CLONE"/*) refuse "clone target is an ancestor of \$HOME ($CLONE)" ;;
esac
case "$C_CLONE" in
  "$C_REPO"|"$C_REPO"/*) refuse "clone target is the repository or inside it ($CLONE)" ;;
esac
case "$C_REPO" in
  "$C_CLONE"|"$C_CLONE"/*) refuse "clone target contains the repository ($CLONE)" ;;
esac

# Dry-run exit, placed before the first destructive step (`rm -rf "$CLONE"`) so the
# guard can be exercised against the live repository with zero risk.
if [ "${AE_KV_GUARD_CHECK:-}" = 1 ]; then
  echo "GUARD_CHECK_PASSED"
  echo "  repo  = $C_REPO"
  echo "  clone = $C_CLONE"
  exit 0
fi

echo "repo:  $REPO"
echo "clone: $CLONE"

echo "=== patch touches these files ==="
grep -a '^diff --git' "$PATCH" || refuse "patch has no 'diff --git' header: $PATCH"

[ -d "$VENDOR" ] || refuse "vendored repo missing: $VENDOR"
git -C "$VENDOR" rev-parse HEAD >/dev/null 2>&1 || refuse "not a git repo: $VENDOR"
git -C "$VENDOR" cat-file -t "$FIXED_OID" >/dev/null 2>&1 \
  || refuse "private fix commit $FIXED_OID absent from vendored repo (proof impossible)"
if [ -n "$(git -C "$VENDOR" status --porcelain -- inference_video.py)" ]; then
  echo "NOTE: vendored working tree has uncommitted edits to inference_video.py;" \
       "tier-2 byte compare reflects those, not the committed fix."
fi

BASE=$(git -C "$VENDOR" rev-parse "$FIXED_OID^")
echo "base:  $BASE"
echo "fixed: $FIXED_OID"

rm -rf "$CLONE"
git clone --no-hardlinks --no-checkout -q "$VENDOR" "$CLONE" || exit 1
git -C "$CLONE" config core.autocrlf false
git -C "$CLONE" config core.eol lf
git -C "$CLONE" checkout -q "$BASE" || exit 1

echo "=== git am tracked patch on pristine base ==="
if ! git -C "$CLONE" \
      -c user.name="AE Knowledge Vault" -c user.email="aekv@local.dev" \
      am "$PATCH"; then
  git -C "$CLONE" am --abort 2>/dev/null
  refuse "git am failed on base $BASE"
fi

echo "=== subject matches the fix commit (bracket prefixes normalized) ==="
# -X utf8 only fixes encoding: without it Python writes cp936 bytes and the
# Chinese subject arrives as mojibake. Line endings are a separate problem.
SUBJ_OK=$(AM_CLONE="$CLONE" VENDOR_DIR="$VENDOR" FIXED="$FIXED_OID" python -X utf8 - <<'PY'
import os, re, subprocess
clone, vendor, fixed = (os.environ[k] for k in ("AM_CLONE", "VENDOR_DIR", "FIXED"))

def norm(s):
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"^\[[^\]]*\][ \t]*", "", s)
    return s.strip()

def subject(repo, rev):
    return subprocess.run(["git", "-C", repo, "log", "-1", "--format=%s", rev],
                          capture_output=True, text=True, encoding="utf-8").stdout

# `git am` decodes the patch's Subject header itself, so both sides are plain
# UTF-8 subjects here; only the bracket prefixes `am` strips need normalizing.
a, b = norm(subject(clone, "HEAD")), norm(subject(vendor, fixed))
print("MATCH" if a and a == b else "DIFFER")
print("  am:   " + a)
print("  fix:  " + b)
PY
)
# Python writes \r\n through a pipe here even under -X utf8 (od -c: the first
# captured line is literally "MATCH\r"), so strip CR before any literal compare.
SUBJ_OK="${SUBJ_OK//$'\r'/}"
echo "$SUBJ_OK"
[ "${SUBJ_OK%%$'\n'*}" = MATCH ] || echo "WARNING: subject mismatch, see above"

FAIL=0
echo "=== tier 1 (authoritative): blob OID patched commit vs fixed commit ==="
FILES=$(git -C "$CLONE" show --name-only --pretty=format: HEAD | grep -v '^$')
for f in $FILES; do
  BLOW=$(git -C "$CLONE" rev-parse "HEAD:$f" 2>/dev/null)
  BLOHI=$(git -C "$VENDOR" rev-parse "$FIXED_OID:$f" 2>/dev/null)
  if [ -z "$BLOHI" ]; then
    echo "MISSING  $f (not present in fix commit)"
    FAIL=$((FAIL + 1))
  elif [ "$BLOW" = "$BLOHI" ]; then
    echo "BLOB MATCH    $f ($BLOW)"
  else
    echo "BLOB DIFFER   $f ($BLOW vs $BLOHI)"
    FAIL=$((FAIL + 1))
  fi
done

echo "=== tier 2 (informational): live worktree bytes, raw then CR-stripped ==="
for f in $FILES; do
  [ -f "$CLONE/$f" ] || continue
  [ -f "$VENDOR/$f" ] || continue
  if cmp -s "$CLONE/$f" "$VENDOR/$f"; then
    echo "BYTES MATCH   $f"
  elif tr -d '\r' < "$CLONE/$f" | cmp -s - <(tr -d '\r' < "$VENDOR/$f"); then
    echo "CRLF ARTIFACT $f (identical ignoring line endings)"
  else
    echo "CONTENT DIFFER $f"
    FAIL=$((FAIL + 1))
  fi
done

echo "RESULT: $([ $FAIL -eq 0 ] && echo PASS || echo FAIL)"
exit $FAIL
