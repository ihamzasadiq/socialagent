"""Dev B owns this module: per-platform OAuth authorization.

Not wired up yet — nothing in orchestrator/ calls this module, since
publish.py currently fakes every publish without needing real credentials.

TODO(Dev B): per-platform authorization-code flow (Twitter/X, LinkedIn,
Discord each have their own) plus wherever tokens end up getting stored
for this hackathon (env vars are probably fine to start). publish.py's
TODO is the thing that will eventually need this.
"""
