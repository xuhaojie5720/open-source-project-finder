#!/usr/bin/env bash
set -e

echo "🚀 Initializing GitHub Codespaces Development Environment..."

# Update pip and install common Python development tools if python is present
if command -v python3 &> /dev/null; then
    echo "📦 Upgrading Python pip..."
    python3 -m pip install --upgrade pip --quiet || true
fi

# Configure git default settings if inside a git repo
if git rev-parse --is-inside-work-tree &> /dev/null; then
    echo "🔧 Setting up Git configuration..."
    git config --local pull.rebase false || true
fi

echo "✅ Environment setup complete! Happy Coding!"
