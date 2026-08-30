#!/usr/bin/env bash
# Worktree inventory gate.
#
# Every git-based integrity check (status --porcelain, ls-files, ls-tree,
# fsck, bundle, the LFS object backup) reported this repository healthy while
# 9212 untracked-and-ignored files under external/ were gone. Gitignored
# content is invisible to git, so "status clean" never meant "worktree
# intact". This script inventories the worktree itself.
#
# Inventory = path + byte size of every regular file outside .git. Sizes, not
# hashes: the defect being caught is a whole tree disappearing, which
# path+size detects exactly, and the worktree holds >1 GB.
#
#   compare (default): exit 1 if any baselined file is gone
#   AE_KV_INV_MODE=snapshot        write/refresh the baseline manifest
#   AE_KV_INV_MODE=snapshot AE_KV_INV_FORCE=1   replace an existing baseline
set -euo pipefail

REPO_DEFAULT="/c/Users/Administrator/Desktop/AE-Knowledge-Vault"
BASE_DEFAULT="/c/Users/Administrator/Desktop/ae-kv-inventory-20260830/manifest.txt"
# Writes to stderr because canon() is called inside $( ) -- a refusal on
# stdout there would be captured into the variable and never shown.
refuse() { echo "REFUSING: $*" >&2; exit 2; }

to_msys() {
  local p="${1//\\//}"
  case "$p" in
    [A-Za-z]:*) printf '%s' "/${p:0:1}${p:2}" | tr 'A-Z' 'a-z' ;;
    *)          printf '%s' "$p" ;;
  esac
}

canon() {
  local raw="$1" p rest resolved q
  case "$raw" in
    ..|../*|*/..|*/../*) refuse "path traversal not supported: $raw" ;;
  esac
  p=$(to_msys "$raw")
  case "$p" in /*) ;; *) p="$(canon "$(pwd)")/$p" ;; esac
  while :; do
    q="$p"
    q="${q//\/\.\//\/}"
    q="${q//\/\///}"
    case "$q" in */.) q="${q%.}" ;; esac
    [ "$q" = "$p" ] && break
    p="$q"
  done
  if [ -e "$p" ]; then
    if [ -d "$p" ]; then ( cd "$p" && pwd -P )
    else ( cd "$(dirname "$p")" && printf '%s/%s\n' "$(pwd -P)" "$(basename "$p")" )
    fi
    return
  fi
  rest="$p"
  while [ -n "$rest" ] && [ "$rest" != "/" ]; do
    if [ -d "$rest" ]; then
      resolved=$(cd "$rest" && pwd -P)
      printf '%s%s\n' "$resolved" "${p#"$rest"}"
      return
    fi
    rest="${rest%/*}"
  done
  printf '%s\n' "$p"
}

# ${VAR:-default} treats "" as unset, so an explicitly empty override would
# silently fall back to the real target. Validate before expanding.
for var in AE_KV_REPO AE_KV_INV_BASE AE_KV_INV_MODE; do
  if [ -n "${!var+x}" ] && [ -z "${!var}" ]; then refuse "$var is set but empty"; fi
done
REPO=$(canon "${AE_KV_REPO-$REPO_DEFAULT}")
BASE=$(canon "${AE_KV_INV_BASE-$BASE_DEFAULT}")
MODE="${AE_KV_INV_MODE:-compare}"
case "$MODE" in compare|snapshot) ;; *) refuse "unknown mode '$MODE'" ;; esac

[ -d "$REPO/.git" ] || refuse "not a git worktree: $REPO"
# This filesystem is case-insensitive, so containment is compared folded: a
# differently spelled drive letter or casing must not open the guard.
REPO_LC="${REPO,,}"
case "${BASE,,}" in "$REPO_LC"|"$REPO_LC"/*)
  refuse "manifest inside the repo would measure itself: $BASE" ;;
esac

if [ "${AE_KV_INV_GUARD_CHECK-x}" = "1" ]; then
  echo "guard ok  REPO=$REPO  BASE=$BASE  MODE=$MODE"
  if [ "$MODE" = snapshot ] && [ -e "$BASE" ] && [ "${AE_KV_INV_FORCE-x}" != 1 ]; then
    echo "guard ok  would refuse to overwrite existing baseline"
  fi
  exit 0
fi

TAB=$(printf '\t')
list_files() {
  ( cd "$REPO" && find . -type f -not -path './.git/*' -printf "%s$TAB%P\n" ) \
    | LC_ALL=C sort -t"$TAB" -k2
}

if [ "$MODE" = snapshot ]; then
  mkdir -p "$(dirname "$BASE")"
  if [ -e "$BASE" ] && [ "${AE_KV_INV_FORCE-x}" != 1 ]; then
    refuse "baseline exists; set AE_KV_INV_FORCE=1 to replace it: $BASE"
  fi
  tmp="$BASE.tmp.$$"
  list_files > "$tmp"
  mv -f "$tmp" "$BASE"
  echo "baseline written  files=$(wc -l < "$BASE")  bytes=$(awk -F"$TAB" '{s+=$1} END {print s+0}' "$BASE")"
  echo "manifest sha256   $(sha256sum "$BASE" | cut -d' ' -f1)"
  echo "RESULT: PASS"
  exit 0
fi

[ -f "$BASE" ] || refuse "no baseline at $BASE (run with AE_KV_INV_MODE=snapshot)"
echo "=== worktree inventory vs baseline $BASE ==="
out=$(mktemp)
list_files | awk '
  BEGIN { FS = "\t"; OFS = "\t" }
  NR == FNR { bsize[$2] = $1; bcount++; next }
  { nsize[$2] = $1; ncount++ }
  END {
    miss = add = chg = 0
    for (p in bsize) if (!(p in nsize)) {
      print "MISSING", p, "(was " bsize[p] " bytes)"; miss++
      n = index(p, "/")
      perdir[(n ? substr(p, 1, n - 1) : p)]++
    }
    for (p in nsize) if (!(p in bsize)) { print "ADDED", p, "(" nsize[p] " bytes)"; add++ }
    for (p in nsize) if ((p in bsize) && bsize[p] != nsize[p]) {
      print "SIZE_CHANGED", p, "(baseline=" bsize[p] " now=" nsize[p] ")"; chg++
    }
    for (d in perdir) print "MISSING_IN", d, perdir[d] " files"
    print "SUMMARY", "baseline=" bcount, "now=" ncount, "missing=" miss, \
          "added=" add, "size_changed=" chg
  }
' "$BASE" - > "$out"
cat "$out"
if grep -q '^MISSING' "$out"; then
  rm -f "$out"
  echo "RESULT: FAIL"
  echo "         Files present in the baseline are gone from the worktree. git" >&2
  echo "         stays silent about this whenever the path is gitignored." >&2
  exit 1
fi
rm -f "$out"
echo "RESULT: PASS"
