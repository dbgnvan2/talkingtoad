#!/usr/bin/env bash
# cycle-runner.sh — Orchestrate a Triad Pod cycle
# 
# This script is invoked by Hermes (the orchestrator) to automate
# the Architect -> Snr Dev handoff. The Claude Code (Developer) step
# remains manual since Claude Code auths via Max OAuth, not an API key.
#
# Usage: ./cycle-runner.sh <cycle_label> <goal_description> [--api-key KEY]
#
# Phases automated by this script:
#   1. Call Gemini (Architect) to write spec from template
#   2. Call Gemini (Snr Dev) to review spec
#   3. Loop spec revision if rejected
#   4. Print the Claude Code prompt for manual paste
#   5. [manual] User pastes into Claude Code, pastes results back
#   6. Call Gemini (Snr Dev) to review implementation
#   7. Call Gemini (Architect) for final spec review
#

set -euo pipefail

CYCLE_LABEL="${1:?Usage: cycle-runner.sh <cycle_label> <goal> [--api-key KEY]}"
GOAL="${2:?Usage: cycle-runner.sh <cycle_label> <goal> [--api-key KEY]}"
REPO_DIR="$HOME/projectsmini1/talkingtoad"
CYCLES_DIR="$REPO_DIR/docs/cycles"
CYCLE_DIR="$CYCLES_DIR/$CYCLE_LABEL"
SPEC_TEMPLATE="$CYCLES_DIR/spec-template.md"
API_KEY="${GEMINI_API_KEY:-}"

# Parse optional --api-key flag
if [ "${3:-}" = "--api-key" ] && [ -n "${4:-}" ]; then
    API_KEY="$4"
fi

if [ -z "$API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY not set. Pass --api-key <key> or export GEMINI_API_KEY."
    exit 1
fi

# Gemini model to use
GEMINI_MODEL="gemini-2.0-flash"

# TODO: Replace with your actual Gemini model
# GEMINI_MODEL="gemini-1.5-pro"

echo "=== Cycle $CYCLE_LABEL ==="
echo "Goal: $GOAL"
echo ""

# Create cycle directory
mkdir -p "$CYCLE_DIR"

# Write state.json
cat > "$CYCLE_DIR/state.json" << STATEEOF
{
  "cycle_label": "$CYCLE_LABEL",
  "description": "$GOAL",
  "phase": "spec_drafting",
  "status": "in_progress",
  "history": [],
  "artifacts": {
    "spec": "spec.md",
    "review": "review.md",
    "implementation": "implementation.md",
    "result": "result.log",
    "final_spec": "final-spec.md"
  }
}
STATEEOF

# ============================================================
# PHASE 1: SPEC DRAFTING (Architect -> Gemini)
# ============================================================
echo "--- Phase 1: Architect drafts spec ---"

# Read the spec template
TEMPLATE_CONTENT=$(cat "$SPEC_TEMPLATE")

# Build the prompt for Gemini
ARCHITECT_PROMPT=$(cat << PROMPT
You are the Architect (Logic Auditor). Your output must be the 4-part spec structure.

Goal for this cycle: $GOAL

Use this template (fill in all sections):

$TEMPLATE_CONTENT

Output ONLY the filled-in spec. No commentary, no extra text.
PROMPT
)

# Call Gemini API
ARCHITECT_RESPONSE=$(curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/$GEMINI_MODEL:generateContent?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg prompt "$ARCHITECT_PROMPT" '{
    "contents": [{"parts": [{"text": $prompt}]}],
    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192}
  }')")

# Extract text from response
SPEC_TEXT=$(echo "$ARCHITECT_RESPONSE" | python3 -c "
import sys, json
resp = json.load(sys.stdin)
for c in resp.get('candidates', []):
    for p in c.get('content', {}).get('parts', []):
        sys.stdout.write(p.get('text', ''))
" 2>/dev/null || echo "ERROR: Failed to parse Gemini response")

if [ -z "$SPEC_TEXT" ]; then
    echo "ERROR: Gemini returned empty spec. Response:"
    echo "$ARCHITECT_RESPONSE" | head -5
    exit 1
fi

# Save spec
echo "$SPEC_TEXT" > "$CYCLE_DIR/spec.md"
echo "Spec written to $CYCLE_DIR/spec.md"
echo ""

# Update state
python3 -c "
import json
with open('$CYCLE_DIR/state.json') as f:
    s = json.load(f)
s['phase'] = 'spec_review'
s['status'] = 'pending'
s['history'].append({'phase': 'spec_drafting', 'status': 'completed', 'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'})
with open('$CYCLE_DIR/state.json', 'w') as f:
    json.dump(s, f, indent=2)
"

# ============================================================
# PHASE 2: SPEC REVIEW (Snr Dev -> Gemini)
# ============================================================
echo "--- Phase 2: Snr Dev reviews spec ---"

SPEC_CONTENT=$(cat "$CYCLE_DIR/spec.md")

# Read the repo's CLAUDE.md for context
CLAUDE_MD=$(head -80 "$REPO_DIR/CLAUDE.md" 2>/dev/null || echo "No CLAUDE.md found")

SENIOR_DEV_PROMPT=$(cat << PROMPT
You are a Senior Software Engineer reviewing a spec. You have read access to the repo.

Repo: TalkingToad (nonprofit SEO crawler, FastAPI/Python + React)
Key conventions from CLAUDE.md:
$CLAUDE_MD

Cycle: $CYCLE_LABEL
Goal: $GOAL

The Architect produced this spec:
$SPEC_CONTENT

Review the spec against the existing codebase. Check:
1. Do the referenced functions/files actually exist?
2. Are there import conflicts or router gaps?
3. Are existing dependencies or conventions respected?
4. Does the spec violate any constraint in CLAUDE.md?

Output exactly one of:

APPROVED
[any notes]

or

REJECTED
Reason: <specific reason>
Issues:
- <issue 1>
- <issue 2>
PROMPT
)

SENIOR_DEV_RESPONSE=$(curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/$GEMINI_MODEL:generateContent?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg prompt "$SENIOR_DEV_PROMPT" '{
    "contents": [{"parts": [{"text": $prompt}]}],
    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
  }')")

REVIEW_TEXT=$(echo "$SENIOR_DEV_RESPONSE" | python3 -c "
import sys, json
resp = json.load(sys.stdin)
for c in resp.get('candidates', []):
    for p in c.get('content', {}).get('parts', []):
        sys.stdout.write(p.get('text', ''))
" 2>/dev/null || echo "ERROR")

# Save review
echo "$REVIEW_TEXT" > "$CYCLE_DIR/review.md"
echo "Review written to $CYCLE_DIR/review.md"
echo ""

# Check if approved
if echo "$REVIEW_TEXT" | grep -q "^APPROVED"; then
    echo "--- Spec APPROVED by Snr Dev ---"
    python3 -c "
import json
with open('$CYCLE_DIR/state.json') as f:
    s = json.load(f)
s['phase'] = 'spec_implementation'
s['status'] = 'pending'
s['history'].append({'phase': 'spec_review', 'status': 'approved', 'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'})
with open('$CYCLE_DIR/state.json', 'w') as f:
    json.dump(s, f, indent=2)
"
else
    echo "--- Spec REJECTED by Snr Dev ---"
    echo "Revision loop required."
    python3 -c "
import json
with open('$CYCLE_DIR/state.json') as f:
    s = json.load(f)
s['phase'] = 'spec_drafting'
s['status'] = 'rejected'
s['history'].append({'phase': 'spec_review', 'status': 'rejected', 'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'})
with open('$CYCLE_DIR/state.json', 'w') as f:
    json.dump(s, f, indent=2)
"
    echo ""
    echo "=== INSTRUCTIONS FOR REVISION ==="
    echo "The Snr Dev rejected the spec with these issues:"
    echo "$REVIEW_TEXT"
    echo ""
    echo "To revise, I (Hermes) will send the spec + review back to the Architect."
    echo "Run: ./cycle-runner.sh $CYCLE_LABEL \"$GOAL\" --revision"
    exit 1
fi

# ============================================================
# PHASE 3: IMPLEMENTATION PROMPT (for manual Claude Code)
# ============================================================
echo ""
echo "============================================================"
echo "=== PHASE 3: MANUAL STEP — Claude Code ==="
echo "============================================================"
echo ""
echo "The spec is approved. Paste the following into Claude Code:"
echo ""
echo "-------- START CLAUDE CODE PROMPT --------"

cat << CLAUDE_PROMPT
You are the Developer. Implement the following approved spec for the TalkingToad repo.

Open repo at: $REPO_DIR

Approved spec:
$(cat "$CYCLE_DIR/spec.md")

Snr Dev review notes:
$(cat "$CYCLE_DIR/review.md" | grep -v "^APPROVED" || echo "No additional notes")

Instructions:
1. Implement the code changes specified in the spec
2. Run pytest
3. If tests fail, fix and re-run (do NOT change the spec)
4. Report results back to the orchestrator

Output PASS or FAIL with specifics.
CLAUDE_PROMPT

echo "-------- END CLAUDE CODE PROMPT --------"
echo ""
echo "After Claude Code finishes, paste its output back to me."
echo "I will handle Phase 4 (Work Review via Snr Dev) and Phase 5 (Final Spec)."
echo "============================================================"
