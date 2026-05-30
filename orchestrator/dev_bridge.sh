#!/bin/bash

# TalkingToad Developer Bridge v2.0
# This script automates the handoff between the Orchestrator and Claude Code.

TASK_FILE="docs/cycles/active_task.md"
OUTPUT_FILE="docs/cycles/task_output.md"

echo "🚀 Developer Bridge v2.0 Active."
echo "📂 Project Root: $(pwd)"
echo "📂 Watching for tasks in $TASK_FILE..."
echo "----------------------------------------------------------------"

while true; do
  if [ -f "$TASK_FILE" ]; then
    # PREVENT CONCURRENCY ISSUES: Create a working copy
    mv "$TASK_FILE" "${TASK_FILE}.processing"
    
    echo ""
    echo "📝 TASK DETECTED at $(date)"
    echo "🛠️ Invoking Claude Code..."
    
    # We use a temp file to capture Claude's reasoning before the final write
    CLAUDE_PROMPT="Read the instructions in ${TASK_FILE}.processing. Execute the code changes required. When finished, write a concise summary of your work (including any new file content) to $OUTPUT_FILE. Ensure the first line of your summary is '[IMPLEMENTATION COMPLETE]'. Do not wait for user input, proceed autonomously."

    # INVOKE CLAUDE
    # We use 'yes' to auto-confirm any simple prompts if they arise
    yes "y" | claude "$CLAUDE_PROMPT"
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
      echo "✅ Claude Code has finished the task (Exit Code: $EXIT_CODE)."
    else
      echo "❌ Claude Code failed (Exit Code: $EXIT_CODE)."
      # If Claude failed but didn't write the output file, we write an error for the Orchestrator
      if [ ! -f "$OUTPUT_FILE" ]; then
        echo "[IMPLEMENTATION COMPLETE]\nERROR: Claude CLI failed with exit code $EXIT_CODE. Please check the terminal log." > "$OUTPUT_FILE"
      fi
    fi

    # Cleanup the processing file
    rm -f "${TASK_FILE}.processing"
    
    echo "🔄 Waiting for Orchestrator to ingest $OUTPUT_FILE..."
    
    # Wait for the orchestrator to ingest and delete the output file before resuming
    while [ -f "$OUTPUT_FILE" ]; do
      sleep 2
    done
    
    echo "✨ Cycle complete. Watching for next task..."
    echo "----------------------------------------------------------------"
  fi
  sleep 2
done
