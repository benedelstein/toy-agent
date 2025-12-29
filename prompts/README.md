# System Prompts

This directory contains the system prompts used by different agent types in the toy-agent framework.

## Prompt Files

- **main_agent.md** - System prompt for the main interactive agent with full toolset (file editing, bash commands, sub-agents, etc.)
- **explore_agent.md** - System prompt for the explore sub-agent, designed to explore codebases and produce summaries
- **plan_agent.md** - System prompt for the planning sub-agent, designed to create detailed task plans

## Usage

Prompts are loaded via `load_system_prompt(prompt_name)` in `main.py`, which:
1. Reads the corresponding `.md` file from this directory
2. Optionally appends `CLAUDE.md` context if it exists in the project root
3. Returns the combined system prompt

## File Format

Prompts are stored as Markdown (`.md`) files for better readability and maintainability. The plain text format makes them easy to edit and version control.
