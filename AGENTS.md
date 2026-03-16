# AGENTS.md - Development Guidelines

## Project Overview

Outlook Mail Extractor is a Windows-only TUI application that extracts emails from Outlook Classic using COM automation. It uses the Textual framework for the UI and python-win32com for Outlook integration.

## Build & Development Commands

### Installation
```bash
# Install dependencies in editable mode
uv pip install -e .

# Or using uv run
uv run pip install -e .
```

### Running the Application
```bash
# Run the TUI application
uv run python app.py

# Run the CLI entry point
uv run outlook-extract
```

### Running Tests
```bash
# Run all tests with pytest
uv run pytest

# Run a single test file
uv run pytest tests/test_core.py

# Run a single test function
uv run pytest tests/test_core.py::test_function_name

# Run tests matching a pattern
uv run pytest -k "test_name_pattern"
```

### Linting & Type Checking
```bash
# Run ruff linter
uv run ruff check .

# Run ruff with auto-fix
uv run ruff check --fix .

# Run mypy type checker
uv run mypy .
```

## Code Style Guidelines

### General Principles
- Python 3.13+ required (uses modern syntax like `|` union types)
- Follow PEP 8 with 88-character line limit (Black-compatible)
- Use type hints everywhere
- Add docstrings to all public functions (Google-style)

### Imports Organization
Order imports in this sequence with blank lines between groups:
1. Standard library
2. Third-party packages
3. Local application imports

```python
# stdlib
from pathlib import Path
import re

# third-party
from bs4 import BeautifulSoup
from textual.app import App, ComposeResult

# local
from outlook_mail_extractor.config import load_config
from .models import CheckStatus
```

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `OutlookClient`, `EmailProcessor`)
- **Functions/methods**: `snake_case` (e.g., `connect()`, `extract_email_data()`)
- **Private methods**: prefix with `_` (e.g., `_perform_check()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_LENGTH = 800`)
- **Dataclass fields**: `snake_case` (e.g., `status: CheckStatus`)

### Type Hints
Use Python 3.13+ union syntax:
```python
# Good
def load_config(config_file: Path | str) -> dict:
def clean_invisible_chars(obj: Any) -> Any:

# Avoid
def load_config(config_file: Union[Path, str]) -> Dict:
```

### Data Models
Use `@dataclass` for simple data containers:
```python
@dataclass
class ConfigStatus:
    status: CheckStatus
    message: str
    path: str = "config.yaml"
```

Use `Enum` for fixed sets of values:
```python
class CheckStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    PENDING = "pending"
```

### Exception Handling
Define custom exceptions inheriting from `Exception`:
```python
class OutlookConnectionError(Exception):
    """Cannot connect to Outlook"""
    pass

class FolderNotFoundError(Exception):
    """Folder not found"""
    pass
```

Use `from e` for exception chaining:
```python
raise OutlookConnectionError(f"Error message\nDetails: {e}") from e
```

### Docstrings
Use Google-style docstrings:
```python
def process_job(
    self,
    job_config: dict,
    dry_run: bool = False,
) -> list[dict]:
    """
    Process a single job configuration.

    Args:
        job_config: Dictionary with name, account, source, destination, limit
        dry_run: If True, don't actually move emails

    Returns:
        List of processed email data dictionaries

    Raises:
        FolderNotFoundError: When source/destination folder doesn't exist
    """
```

### File Structure
```
outlook_mail_extractor/
├── __init__.py       # Public API exports
├── config.py         # Configuration loading/validation
├── core.py           # Outlook COM connection & email processing
├── parser.py         # HTML/text parsing utilities
├── models.py         # Data models (dataclasses, enums)
└── screens.py        # Textual UI screens

app.py                # Application entry point
config.yaml           # Runtime configuration
```

### Error Handling Patterns
- Validate config at startup in `validate_config()`
- Use try/finally for resource cleanup (e.g., disconnecting COM)
- Return early on error conditions when possible
- Log errors with descriptive messages

### UI Development (Textual)
- Use `ComposeResult` type hint for `compose()` methods
- Use `id` attributes for querying widgets
- Prefix event handlers with `on_` (e.g., `on_button_pressed()`)

## Architecture Notes

### Outlook COM Connection
- Only works on Windows with Outlook Classic (not New Outlook)
- Requires Outlook to be running
- Use `pythoncom.CoInitialize()` / `CoUninitialize()` for thread safety

### Configuration
- YAML-based config in `config.yaml`
- Required fields: `name`, `account`, `source`, `destination`, `limit`
- Sample config in `config.yaml.sample`

## Testing Guidelines
- Tests go in `tests/` directory
- Use pytest as test runner
- Mock Outlook COM objects when possible
- Test error cases (missing config, connection failures)
