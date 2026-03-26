# Mailslide

A Windows + Outlook Classic automation tool for turning repetitive email work into reliable workflows.
Use configurable jobs and optional LLM plugins to classify, route, summarize, and structure email processing.

Language: English (`README.en.md`) | Traditional Chinese (`README.md`)

## Why Mailslide

- Standardize Outlook processing with repeatable job-based workflows.
- Go beyond classification: move folders, create appointments, export JSON/CSV/Excel.
- Keep deployment flexible: OpenAI-compatible APIs or local models (Ollama, llama.cpp).
- Friendly for non-developers: initialize and edit configs directly in the TUI.

## Typical use cases

- Operations and assistants: triage meeting requests, alerts, and routine inbox traffic.
- PMs and sales: convert email streams into trackable events and summaries.
- Engineering and support: auto-tag and prioritize incoming threads.

## 30-second start

```bash
uv sync
uv run app.py
```

Then in TUI:

1. Open **About** and click **Initialize Config**.
2. Open **Configuration** and set Jobs / LLM / Plugins.
3. Return to **Home** and run a job.

## Results Preview

- Home run and logs: show one job run with processing summary
- Configuration forms: show Jobs / LLM / Plugins setup screens
- Plugin editor: show Prompt Profiles and validate/save flow

![Home Run](docs/assets/home-run.png)
![Configuration](docs/assets/configuration.png)
![Plugin Editor](docs/assets/plugin-editor.png)

## Plugin Capability Matrix

| Plugin | Primary purpose | LLM required | Typical output |
|---|---|---|---|
| `add_category` | Classify emails and add categories | Yes | Outlook category tags |
| `move_to_folder` | Decide and move target folders | Yes | Folder move result |
| `create_appointment` | Create calendar items from email content | Yes | Outlook calendar items |
| `event_table` | Extract event data into a table | Yes | `output/events.xlsx` |
| `summary_file` | Generate summaries and priorities | Yes | `output/email_summaries.csv` |
| `write_file` | Export raw email data | No | `output/*.json` |

## Full Guide

- English: `GUIDE.en.md`
- Traditional Chinese: `GUIDE.md`

The TUI `Guide` tab now prefers `GUIDE.en.md` / `GUIDE.md` and falls back to `README` files for compatibility.

## Requirements

- Windows
- Outlook Classic (not New Outlook)
- Outlook must stay open while running

## License

`GPL-3.0-or-later`. See `LICENSE`.
