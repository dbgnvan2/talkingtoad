#!/usr/bin/env bash
#
# run_compiler.sh — Gemini Compiler pipeline (per CLAUDE.md).
#
# Feeds docs/functional-specification.md + all docs/pending/*.md into a fresh
# Gemini context; the compiled output REPLACES functional-specification.md and
# docs/pending/ is cleared. functional-specification.md is normally READ-ONLY;
# this script is the one sanctioned exception.
#
# Safety:
#   - backs up the current spec to docs/.compiler-backups/<timestamp>/
#   - aborts if there are no pending specs
#   - aborts if Gemini output is empty or implausibly short (truncation guard)
#   - only clears docs/pending/ AFTER a successful replace
#
# Usage: ./scripts/run_compiler.sh
set -euo pipefail

ROOT="/Users/davemini/ProjectsMini1/TalkingToad"
cd "$ROOT"

SPEC="docs/functional-specification.md"
PENDING_DIR="docs/pending"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="docs/.compiler-backups/$TS"

# --- preconditions --------------------------------------------------------
pending_files=$(ls "$PENDING_DIR"/*.md 2>/dev/null | grep -v '\.gitkeep' || true)
if [[ -z "$pending_files" ]]; then
  echo "No pending specs in $PENDING_DIR — nothing to compile."
  exit 0
fi
if ! command -v gemini >/dev/null 2>&1; then
  echo "ERROR: gemini CLI not found on PATH." >&2
  exit 1
fi

orig_lines=$(wc -l < "$SPEC")
echo "Compiler: spec=$orig_lines lines, $(echo "$pending_files" | wc -l | tr -d ' ') pending specs."

# --- build the prompt -----------------------------------------------------
PROMPT_FILE="$(mktemp)"
OUT_FILE="$(mktemp)"
trap 'rm -f "$PROMPT_FILE" "$OUT_FILE"' EXIT

{
  echo "You are the TalkingToad Functional-Specification Compiler."
  echo "Merge the APPROVED PENDING SPECS below into the CURRENT FUNCTIONAL SPECIFICATION,"
  echo "producing a single updated functional specification in GitHub-flavoured Markdown."
  echo ""
  echo "RULES:"
  echo "- Preserve the existing document's structure, section order, and frontmatter."
  echo "- Integrate each pending spec's shipped behaviour into the right section; do NOT"
  echo "  append them verbatim as a changelog. Reflect the feature as CURRENT behaviour."
  echo "- Update the frontmatter 'last_reviewed' date to today: $(date -u +%Y-%m-%d)."
  echo "- Do NOT drop or summarise away any existing content that is still accurate."
  echo "- Keep it factual; no marketing language."
  echo "- Output ONLY the final Markdown document. No preamble, no code fences around the whole thing."
  echo ""
  echo "=================== CURRENT FUNCTIONAL SPECIFICATION ==================="
  cat "$SPEC"
  echo ""
  echo "=================== APPROVED PENDING SPECS (merge these) ==================="
  for f in $pending_files; do
    echo ""
    echo "----- BEGIN $f -----"
    cat "$f"
    echo "----- END $f -----"
  done
} > "$PROMPT_FILE"

echo "Compiler: invoking gemini (this can take a minute)..."
gemini -p "$(cat "$PROMPT_FILE")" > "$OUT_FILE" 2> >(grep -v "256-color" >&2 || true)

# --- truncation / sanity guard --------------------------------------------
# Strip a leading ```markdown fence if the model added one.
sed -i '' -e '1{/^```\(markdown\)\{0,1\}$/d}' -e '${/^```$/d}' "$OUT_FILE" 2>/dev/null || true

out_lines=$(wc -l < "$OUT_FILE")
min_lines=$(( orig_lines * 70 / 100 ))   # output must be >= 70% of original
if [[ "$out_lines" -lt "$min_lines" ]]; then
  echo "ABORT: compiled output is only $out_lines lines (< $min_lines = 70% of $orig_lines)." >&2
  echo "       Likely truncated or an error. Spec NOT replaced. Output saved to: $OUT_FILE" >&2
  cp "$OUT_FILE" "docs/.compiler-FAILED-$TS.md"
  echo "       Copy at docs/.compiler-FAILED-$TS.md for inspection." >&2
  exit 1
fi
if ! head -5 "$OUT_FILE" | grep -q "Functional Specification"; then
  echo "WARN: output does not contain the expected 'Functional Specification' title in the first 5 lines." >&2
  echo "      Proceeding but review carefully (backup retained)." >&2
fi

# --- commit the swap ------------------------------------------------------
mkdir -p "$BACKUP_DIR"
cp "$SPEC" "$BACKUP_DIR/functional-specification.md"
cp $pending_files "$BACKUP_DIR/" 2>/dev/null || true

cp "$OUT_FILE" "$SPEC"
# Clear pending (keep .gitkeep)
for f in $pending_files; do rm -f "$f"; done

echo "Compiler: DONE."
echo "  spec: $orig_lines -> $out_lines lines"
echo "  backup: $BACKUP_DIR"
echo "  pending/ cleared ($(echo "$pending_files" | wc -l | tr -d ' ') specs folded in)"
