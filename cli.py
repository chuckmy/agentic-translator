"""CLI for managing TranslationModels and Engines (v0.10.0).

Usage:
    at model new <id> [--source ja --target en --display "..." --by you@co]
    at model list
    at model show <id>
    at model edit <id>
    at model lock <id> --bump patch|minor|major [--by you@co]
    at model unlock <id>
    at model compile <id> [--by you@co]

    at engine list
    at engine show <id>@<version>
    at engine verify <id>@<version>
    at engine remove <id>@<version>

Install entry point handled by `python -m cli ...` or via the `at` alias.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from model import (
    Engine, TranslationModel,
    engines_dir, list_engines, list_models, models_dir, remove_engine,
)

app = typer.Typer(add_completion=False, help="Agentic Translator — Model/Engine ops")
model_app = typer.Typer(help="Manage editable TranslationModels")
engine_app = typer.Typer(help="Manage compiled, immutable Engines")
app.add_typer(model_app, name="model")
app.add_typer(engine_app, name="engine")

console = Console()


def _err(msg: str) -> None:
    console.print(f"[red]error:[/red] {msg}")
    raise typer.Exit(1)


def _ok(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


# ---------------------------------------------------------------------------
# model subcommands
# ---------------------------------------------------------------------------

@model_app.command("new")
def model_new(
    id: str,
    source: str = typer.Option("Japanese", help="Source language"),
    target: str = typer.Option("English", help="Target language"),
    locale: str = typer.Option("", help="Target locale (e.g. en-US)"),
    display: str = typer.Option("", help="Human-readable display name"),
    description: str = typer.Option("", help="Free-form description"),
    by: str = typer.Option("", help="Created-by identifier (email or handle)"),
):
    """Scaffold a new Model directory under models/<id>/."""
    try:
        m = TranslationModel.new(
            id=id,
            display_name=display or id,
            description=description,
            source_language=source,
            target_language=target,
            locale=locale,
            created_by=by,
        )
    except FileExistsError as e:
        _err(str(e))
    _ok(f"Created model [bold]{m.id}[/bold] at {m.model_dir}")
    console.print(
        f"  version={m.version} · state=draft · "
        f"source={source} → target={target} ({locale or 'no locale'})"
    )
    console.print(
        "Next: edit [cyan]spec/narrative.md[/cyan] (or use the Streamlit UI in "
        "Model-dev mode), drop a glossary into [cyan]glossary/terms.csv[/cyan], "
        f"then run [bold]at model lock {m.id} --bump minor[/bold]."
    )


@model_app.command("list")
def model_list():
    """List all Models in models/."""
    models = list_models()
    if not models:
        console.print(f"No models found at {models_dir()}.")
        return
    table = Table(title="Models")
    table.add_column("id", style="bold")
    table.add_column("version")
    table.add_column("state")
    table.add_column("languages")
    table.add_column("locked at")
    for m in models:
        state = "locked" if m.is_locked else "draft"
        languages = f"{m.manifest.get('source_language','?')} → {m.manifest.get('target_language','?')}"
        locked_at = m.manifest.get("locked_at") or ""
        if m.is_locked:
            drift, _ = m.has_drift()
            if drift:
                state = "[yellow]locked (drift)[/yellow]"
        table.add_row(m.id, m.version, state, languages, str(locked_at))
    console.print(table)


@model_app.command("show")
def model_show(id: str):
    """Show a Model's manifest."""
    try:
        m = TranslationModel.load(id)
    except FileNotFoundError as e:
        _err(str(e))
    console.print(f"[bold]{m.id}[/bold]  version={m.version}  state={m.manifest.get('lock_state')}")
    console.print(f"path: {m.model_dir}")
    console.print(f"display: {m.manifest.get('display_name')}")
    console.print(f"languages: {m.manifest.get('source_language')} → {m.manifest.get('target_language')} ({m.manifest.get('locale') or 'no locale'})")
    console.print(f"llm: {m.manifest.get('llm')}")
    console.print(f"pipeline: {m.manifest.get('pipeline')}")
    if m.is_locked:
        drift, files = m.has_drift()
        if drift:
            console.print(f"[yellow]DRIFT[/yellow] from locked hashes: {files}")
        else:
            console.print(f"[green]✓[/green] files match locked hashes (hash={m.manifest.get('hash')})")
    if m.manifest.get("engines"):
        console.print("compiled engines:")
        for e in m.manifest["engines"]:
            console.print(f"  - {m.id}@{e.get('version')}  ({e.get('compiled_at')})")


@model_app.command("edit")
def model_edit(id: str):
    """Open the spec narrative in $EDITOR."""
    try:
        m = TranslationModel.load(id)
    except FileNotFoundError as e:
        _err(str(e))
    if m.is_locked:
        _err(f"Model {id} is locked. Run `at model unlock {id}` first.")
    editor = os.environ.get("EDITOR", "vi")
    subprocess.run([editor, str(m.spec_narrative_path)])


@model_app.command("lock")
def model_lock(
    id: str,
    bump: str = typer.Option(..., "--bump", "-b", help="patch | minor | major"),
    by: str = typer.Option("", help="Locked-by identifier"),
):
    """Lock the Model with a semver bump and freeze its source hashes."""
    try:
        m = TranslationModel.load(id)
    except FileNotFoundError as e:
        _err(str(e))
    try:
        m.lock(bump=bump, by=by)
    except (RuntimeError, ValueError) as e:
        _err(str(e))
    _ok(f"Locked {m.id} at version {m.version}")
    console.print(f"  hash: {m.manifest.get('hash')}")
    console.print(f"Next: [bold]at model compile {m.id}[/bold] to produce an Engine.")


@model_app.command("unlock")
def model_unlock(id: str):
    """Return the Model to draft state. Existing Engines are unaffected."""
    try:
        m = TranslationModel.load(id)
    except FileNotFoundError as e:
        _err(str(e))
    if not m.is_locked:
        console.print(f"{m.id} is already in draft.")
        return
    m.unlock()
    _ok(f"Unlocked {m.id} (still at version {m.version}; bump on next lock).")


@model_app.command("compile")
def model_compile(
    id: str,
    by: str = typer.Option("", help="Compiled-by identifier"),
):
    """Compile a locked Model into an immutable Engine."""
    try:
        m = TranslationModel.load(id)
    except FileNotFoundError as e:
        _err(str(e))
    try:
        e = Engine.compile_from(m, compiled_by=by)
    except (RuntimeError, FileExistsError) as exc:
        _err(str(exc))
    _ok(f"Compiled engine [bold]{e.display_id}[/bold] at {e.engine_dir}")
    console.print(f"  engine_hash: {e.seal.get('engine_hash')}")
    console.print(f"  system_version: {e.seal.get('system_version')}")


# ---------------------------------------------------------------------------
# engine subcommands
# ---------------------------------------------------------------------------

@engine_app.command("list")
def engine_list():
    """List all compiled Engines in engines/."""
    engines = list_engines()
    if not engines:
        console.print(f"No engines found at {engines_dir()}.")
        return
    table = Table(title="Engines")
    table.add_column("id@version", style="bold")
    table.add_column("compiled_at")
    table.add_column("compiled_by")
    table.add_column("system_ver")
    table.add_column("integrity")
    for e in engines:
        ok, drifted = e.verify()
        integrity = "[green]ok[/green]" if ok else f"[red]DRIFT ({len(drifted)})[/red]"
        table.add_row(
            e.display_id,
            str(e.seal.get("compiled_at", "")),
            str(e.seal.get("compiled_by", "")),
            str(e.seal.get("system_version", "")),
            integrity,
        )
    console.print(table)


@engine_app.command("show")
def engine_show(ref: str = typer.Argument(..., help="<id>@<version>")):
    """Show an Engine's seal and manifest summary."""
    try:
        e = Engine.load(ref)
    except FileNotFoundError as exc:
        _err(str(exc))
    console.print(f"[bold]{e.display_id}[/bold]")
    console.print(f"path: {e.engine_dir}")
    console.print(f"compiled_at: {e.seal.get('compiled_at')}")
    console.print(f"compiled_by: {e.seal.get('compiled_by')}")
    console.print(f"system_version: {e.seal.get('system_version')}")
    console.print(f"engine_hash: {e.seal.get('engine_hash')}")
    console.print(f"model_hash (at compile): {e.seal.get('compiled_from', {}).get('model_hash')}")
    console.print(f"llm: {e.llm_settings()}")
    console.print(f"pipeline: {e.pipeline_kwargs()}")


@engine_app.command("verify")
def engine_verify(ref: str = typer.Argument(..., help="<id>@<version>")):
    """Re-hash an Engine and report drift."""
    try:
        e = Engine.load(ref)
    except FileNotFoundError as exc:
        _err(str(exc))
    ok, drifted = e.verify()
    if ok:
        _ok(f"{e.display_id} integrity verified.")
    else:
        console.print(f"[red]DRIFT in {e.display_id}:[/red]")
        for f in drifted:
            console.print(f"  - {f}")
        raise typer.Exit(2)


@engine_app.command("remove")
def engine_remove(
    ref: str = typer.Argument(..., help="<id>@<version>"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete an Engine snapshot. Cannot be undone."""
    try:
        e = Engine.load(ref)
    except FileNotFoundError as exc:
        _err(str(exc))
    if not yes:
        ans = typer.prompt(f"Really delete {e.display_id} at {e.engine_dir}? Type 'yes' to confirm")
        if ans.strip().lower() != "yes":
            console.print("Aborted.")
            raise typer.Exit(1)
    remove_engine(e)
    _ok(f"Removed {e.display_id}")


def main():
    app()


if __name__ == "__main__":
    main()
