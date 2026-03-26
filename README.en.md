# mailslide

Extract, analyze, and automate Outlook emails on Windows, with optional LLM-powered plugins.

Language: English (`README.en.md`) | Traditional Chinese (`README.md`)

## Quick Start (TUI)

```bash
uv sync
uv run app.py
```

1. Open the **About** tab and click **Initialize Config**.
2. Open **Configuration -> General** to add/edit jobs, then click **Validate** and **Save**.
3. If you need LLM features, open **Configuration -> LLM** and click **Test Connection**.
4. If you need plugins, open **Configuration -> Plugins**, choose one, and click **Edit Config**.

## Install `uv` (Required)

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management.

```powershell
# PowerShell (Windows)
irm https://astral.sh/uv/install.ps1 | iex

# or via pip
pip install uv

# or via winget
winget install astral-sh.uv
```

Install dependencies:

```bash
uv sync
```

> Use `uv sync` (not `uv pip install`) to keep dependency versions consistent.

## Initialize Configuration

### Option A: TUI (Recommended)

1. Run `uv run app.py`
2. Go to the **About** tab
3. Click **Initialize Config**
4. The app copies all `*.yaml.sample` files to `*.yaml`

### Option B: Manual Copy

```bash
# main config
copy config\config.yaml.sample config\config.yaml

# LLM config
copy config\llm-config.yaml.sample config\llm-config.yaml

# logging config
copy config\logging.yaml.sample config\logging.yaml

# plugin configs
copy config\plugins\*.yaml.sample config\plugins\
```

## CLI Mode

Use CLI for one-off runs:

```bash
# default config
uv run mailslide

# custom config file
uv run mailslide --config path/to/config.yaml

# dry run (read only, do not move mails)
uv run mailslide --dry-run

# write run result to JSON
uv run mailslide --output result.json

# extract only, do not move mails
uv run mailslide --no-move
```

## Python Import Migration

Use the new import path `mailslide` for new code:

```python
from mailslide import load_config, LLMClient
```

Minimal runnable example:

```python
from pathlib import Path

from mailslide import load_config


config = load_config(Path("config/config.yaml"))
print(f"jobs: {len(config.get('jobs', []))}")
```

The legacy path `outlook_mail_extractor` is still supported during the compatibility window and will be removed in a future major release.

## Core `config.yaml` Example

```yaml
llm_mode: per_plugin

jobs:
  - name: "My Job"
    account: "your@email.com"
    source: "Inbox"
    destination: "Inbox/processed"
    manual_review_destination: "Inbox/manual_review"
    limit: 10
    plugins:
      - add_category
```

Key fields:

| Field | Description |
|---|---|
| `name` | Job name |
| `enable` | Enable job (`true`/`false`, default `true`) |
| `account` | Outlook account email or PST display name |
| `source` | Source folder (for example, `Inbox`) |
| `destination` | Destination folder after processing (optional) |
| `manual_review_destination` | Folder for skipped/failed LLM outcomes (optional) |
| `limit` | Max emails processed per run |
| `llm_mode` | LLM mode (`per_plugin` default, `share_deprecated` legacy) |
| `ui_language` | UI language (`zh-TW` / `en-US`, default `zh-TW`) |
| `plugins` | Enabled plugins (optional) |

## LLM Call Modes

- `per_plugin` (default): each LLM-enabled plugin calls LLM independently.
- `share_deprecated` (legacy): one LLM call shared across plugins for one email.

`llm_mode` can be set at:

- global: `config.llm_mode`
- per job override: `job.llm_mode`

Legacy values `shared` / `shared_legacy` are still accepted and treated as `share_deprecated` with warning logs.

## Localization (gettext + Babel)

The project uses key-based i18n (for example `app.title`).

- Runtime: `gettext` (falls back to `outlook_mail_extractor/locales/*.yaml` if catalog is not compiled)
- Development: `Babel` for `po/mo`

Temporarily override language in CLI:

```bash
uv run mailslide --lang en-US
```

Or set in `config/config.yaml`:

```yaml
ui_language: en-US
```

Common Babel commands:

```bash
pybabel extract -F babel.cfg -o outlook_mail_extractor/locales/gettext/messages.pot .
pybabel init -i outlook_mail_extractor/locales/gettext/messages.pot -d outlook_mail_extractor/locales/gettext -D messages -l zh_TW
pybabel init -i outlook_mail_extractor/locales/gettext/messages.pot -d outlook_mail_extractor/locales/gettext -D messages -l en_US
pybabel update -i outlook_mail_extractor/locales/gettext/messages.pot -d outlook_mail_extractor/locales/gettext -D messages
pybabel compile -d outlook_mail_extractor/locales/gettext -D messages
```

Windows PowerShell helper script:

```powershell
./scripts/i18n.ps1 all
```

## LLM Configuration (Optional)

Edit in TUI (**Configuration -> LLM**) or manually in `config/llm-config.yaml`:

```yaml
api_base: "http://localhost:11434/v1"
api_key: ""
model: "llama3"
```

Supports OpenAI-compatible endpoints such as Ollama and LM Studio.

## Built-in Plugins

| Plugin | Purpose |
|---|---|
| `add_category` | Analyze email and add categories |
| `move_to_folder` | Decide target folder with AI |
| `create_appointment` | Create Outlook appointments from email content |
| `event_table` | Append extracted event data to Excel (with Outlook link) |
| `write_file` | Save email data as JSON |
| `summary_file` | Append AI summaries to CSV |

## Prompt Profiles (Per Plugin)

LLM plugins can define multiple prompt profiles so different jobs use different prompts.

Supported plugins:

- `add_category`
- `move_to_folder`
- `create_appointment`
- `event_table`
- `summary_file`

Plugin config example (`config/plugins/<name>.yaml.sample`):

```yaml
default_prompt_profile: general_v1

prompt_profiles:
  general_v1:
    version: 1
    description: "General classification"
    system_prompt: |
      You are an email classification assistant...

  invoice_v1:
    version: 1
    description: "Invoice handling"
    system_prompt: |
      You are an invoice classifier. Prioritize payment intent...
```

Job-level override example (`config/config.yaml`):

```yaml
jobs:
  - name: "General Mail"
    plugins:
      - add_category

  - name: "Invoices"
    plugins:
      - add_category
    plugin_prompt_profiles:
      add_category: invoice_v1
```

Resolution order:

1. `job.plugin_prompt_profiles[plugin]`
2. `plugin.default_prompt_profile`
3. `plugin.system_prompt` fallback

## TUI Tabs

Run `uv run app.py` to open the TUI.

| Key | Tab |
|---|---|
| `H` | Home |
| `S` | Schedule |
| `G` | Guide |
| `C` | Configuration |
| `A` | About |
| `L` | Language |

## Requirements

- Windows
- Outlook Classic (not New Outlook)
- Outlook must remain open during execution

## License

This project is licensed under `GPL-3.0-or-later`. See `LICENSE` for details.

## Local LLM via `llama.cpp`

You can run fully local inference (no external API needed).

1. Download `llama-server.exe` from [llama.cpp Releases](https://github.com/ggml-org/llama.cpp).
2. Start server (example):

```powershell
# basic
.\llama-server.exe -m .\Qwen3.5-2B-Q8_0.gguf --port 8080

# disable thinking mode (recommended)
.\llama-server.exe -m .\Qwen3.5-2B-Q8_0.gguf --port 8080 --chat_template_kwargs '{"enable_thinking":false}'
```

3. Configure `config/llm-config.yaml`:

```yaml
api_base: "http://localhost:8080/v1"
api_key: "any"
model: "qwen3"
```

Notes:

- `api_base` must include `/v1`
- `api_key` can be any string for local `llama.cpp`
- `model` should match your loaded model
