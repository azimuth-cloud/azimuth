#!/usr/bin/env bash

set -e

# Always use the truncated git hash as a tag
SHORT_SHA="${GITHUB_SHA:0:8}"
TAGS="$REPOSITORY:$SHORT_SHA"

# If the ref is a head, and the branch name as a tag
# If the branch is master, also tag with latest
if [[ "$GITHUB_REF" == refs/heads/* ]]; then
    BRANCH_NAME="${GITHUB_REF#refs/heads/}"
    TAGS="$TAGS,$REPOSITORY:$BRANCH_NAME"
    if [ "$BRANCH_NAME" = "master" ]; then
      TAGS="$TAGS,$REPOSITORY:latest"
    fi  
fi

# If the ref is a tag, add the git tag as a docker tag
if [[ "$GITHUB_REF" == refs/tags/* ]]; then
    TAGS="$TAGS,$REPOSITORY:${GITHUB_REF#refs/tags/}"
fi

# Echo the tags as a GitHub actions output
echo "::set-output name=TAGS::$TAGS"
