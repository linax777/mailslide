# RC Evidence Template: <version>-rcN

## Environment

- OS:
- Python:
- Tooling (`uv --version`):

## Install Command

```bash
uv tool install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple mailslide
```

## Job Config Marker

- LLM-enabled job marker:
- Non-LLM baseline marker:

## Pass/Fail Output Snippet

### Success Path

```text
dependency_guard_passed
```

### Guard Failure Path

```text
dependency_guard_failed
DEPENDENCY_GUARD_FAILED
```

### Unevaluable-Contract Path

```text
dependency_guard_failed
DEPENDENCY_GUARD_FAILED
```

## Timestamp

- UTC:

## Notes

- Local source-mode sanity run status:
- Reviewer:
