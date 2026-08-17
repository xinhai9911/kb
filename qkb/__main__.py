"""Entry point — `python -m qkb <subcommand>`. Mirrors qkb.cli."""
from .cli import main

raise SystemExit(main())