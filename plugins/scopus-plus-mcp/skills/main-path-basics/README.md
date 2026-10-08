# main-path-basics

A Claude skill for main path analysis: query Scopus, build the citation network, find the main path,
draw it. Made by Michal Hron for the tutorial "Map a research field with Claude".

It ships with the scopus-plus-mcp plugin for Claude Code. For Claude Desktop, zip this folder and
upload it as a skill, then install the Scopus Plus MCP server from the repository README.

Scripts run on Python 3 with matplotlib. `python3 scripts/main_path.py --selftest` checks the install.
