#!/usr/bin/env bash
# List top-level directories in the repository.
# Excludes hidden directories (starting with .) and files.
for item in */; do
    # Remove trailing slash
    dir="${item%/}"
    echo "$dir"
done
