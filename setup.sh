#!/bin/bash
# Setup script for toy-agent development

set -e

echo "Setting up toy-agent..."

# Install dependencies
uv sync

# Configure git hooks
git config core.hooksPath .githooks

echo "Done! Run 'uv run toy_agent/main.py' to start."
