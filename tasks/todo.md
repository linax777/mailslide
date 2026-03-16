# Tasks - Outlook Mail Extractor LLM Integration

## Phase 1: Configuration Files Separation

- [ ] **1.1** Expand `config.yaml` - jobs only contain basic info (name, account, filter, plugins, limit)
- [ ] **1.2** Create `llm.yaml` - global LLM API settings (provider, api_base, model, api_key, timeout)
- [ ] **1.3** Create `filters.yaml` - all job filter conditions (from, subject_contains, is_unread, etc.)
- [ ] **1.4** Create `config/plugins/` directory for plugin configs

## Phase 2: LLM Module

- [ ] **2.1** Create `outlook_mail_extractor/llm.py` - LLM API integration
- [ ] **2.2** Support OpenAI compatible API (llama.cpp, LM Studio, Ollama)
- [ ] **2.3** Implement chat completion with system prompt + email content

## Phase 3: Plugin System

- [ ] **3.1** Create `outlook_mail_extractor/plugins/` package
- [ ] **3.2** Create `plugins/base.py` - BasePlugin abstract class with system_prompt
- [ ] **3.3** Create `plugins/__init__.py` - plugin registry
- [ ] **3.4** Implement MoveToFolderPlugin - move emails to folder based on LLM response
- [ ] **3.5** Implement AddCategoryPlugin - add categories to emails
- [ ] **3.6** Implement CreateAppointmentPlugin - create calendar appointments

## Phase 4: Core Integration

- [ ] **4.1** Update `config.py` - load and validate separated config files
- [ ] **4.2** Update `core.py` - integrate LLM analysis into email processing flow
- [ ] **4.3** Update `models.py` - add LLM response data models

## Phase 5: UI Updates

- [ ] **5.1** Update `screens.py` - show LLM analysis status
- [ ] **5.2** Add LLM configuration screen
- [ ] **5.3** Add filter management screen

---

## File Structure After Changes

```
config/
├── config.yaml           # Jobs basic info
├── llm.yaml              # LLM API settings
├── filters.yaml          # Filter conditions
└── plugins/              # Plugin configs
    ├── move_to_folder.yaml
    ├── add_category.yaml
    └── create_appointment.yaml

outlook_mail_extractor/
├── __init__.py
├── config.py
├── core.py
├── parser.py
├── models.py
├── screens.py
├── llm.py                # NEW: LLM integration
└── plugins/              # NEW: Plugin system
    ├── __init__.py
    ├── base.py
    ├── move.py
    ├── category.py
    └── calendar.py
```
