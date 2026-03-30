# RC Evidence Artifacts

Store one evidence artifact per release candidate at:

- `docs/releases/evidence/<version>-rcN.md`

Example:

- `docs/releases/evidence/0.4.0-rc2.md`

Each artifact must include:

1. `Environment`
2. `Install Command`
3. `Job Config Marker`
4. `Pass/Fail Output Snippet`
5. `Timestamp`
6. Success token: `dependency_guard_passed`
7. Failure token: `dependency_guard_failed`

Use `docs/releases/evidence/template-rc-evidence.md` as the starting point.

Validation command:

```bash
uv run python scripts/validate_rc_evidence.py --version v0.4.0rc2
```
