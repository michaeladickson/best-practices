# CLI Patterns (Click)

## Standard Structure

```python
import click

@click.command()
@click.option("--days", default=7, help="Look back N days")
@click.option("--dry-run", is_flag=True, help="Preview without side effects")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def main(days: int, dry_run: bool, json_output: bool):
    """Docstring becomes --help text."""
    ...

if __name__ == "__main__":
    main()
```

## Command Groups

```python
@click.group()
def cli():
    """Tool description."""
    pass

@cli.command()
def categorize():
    """Categorize transactions."""
    ...

@cli.command()
def report():
    """Generate spending report."""
    ...
```

Invoke: `python -m module_name categorize --days 90`

## Common Flags

Every CLI tool should support:
- `--dry-run` — preview without writes/sends
- `--days N` — lookback period
- `--json-output` — machine-readable output (optional)

Pipeline/sync tools should also support:
- `--skip-{step}` — skip specific pipeline stages
- `--context path.yaml` — swap configuration file

## Output Formatting

- Use `click.echo()` for all output
- Pretty-print tables with ASCII formatting for terminal
- Support `--json-output` for scripting/piping

## Module Entry Points

```python
# __main__.py
from module.main import cli
cli()
```

Invoke with: `python -m module`

## Where Used

- **crumbl-ops**: Daily sync CLI with `--skip-*` flags
- **wealth-mgmt**: Spending CLI with group commands
- **best-practices**: Digest CLI with `--dry-run` and `--context`
