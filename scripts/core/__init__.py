"""cinegraph core — the vault-free analytics engine.

Pure Python (stdlib only) over a `Film` schema: the taste model, and (added
incrementally) film similarity, taste islands, and recommendation scoring. Nothing here
reads the Obsidian vault or the filesystem — callers pass in a `list[Film]`, so the same
engine can be fed from Markdown notes today or a database later (see .ai/SAAS_PLAN.md).
"""
