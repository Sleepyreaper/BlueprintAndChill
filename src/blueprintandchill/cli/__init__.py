"""CLI entrypoint package for BlueprintAndChill."""

from __future__ import annotations

import typer

app = typer.Typer(
 name="blueprintandchill",
 help=(
 "BlueprintAndChill command-line interface. "
 "Foundational scaffold for future Azure Landing Zone and subscription-vending workflows."
 ),
 no_args_is_help=True,
)


@app.callback()
def main() -> None:
 """CLI root callback placeholder for future command wiring."""
 return None