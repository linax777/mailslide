# Attachment Recall Release Gate

This directory stores RC attachment-recall gate artifacts.

## Files

- `baseline.json`: approved baseline versions used by CI gate.
- `template-attachment-recall-report.md`: report template for each RC cycle.
- `<version>-rcN.md`: release-candidate recall report, for example `0.4.1-rc4.md`.

## Required report fields

Each report must include a machine-readable JSON block with:

- `sample_protocol_version`
- `label_set_version`
- `labeled_downloadable_count`
- `saved_downloadable_count`
- `completeness_ratio`
- `gate_verdict`

## Gate rules

- `labeled_downloadable_count >= 200`
- `saved_downloadable_count / labeled_downloadable_count >= 0.98`
- `sample_protocol_version` matches `baseline.json`
- `label_set_version` matches `baseline.json`
- `gate_verdict` must match computed outcome (`pass` / `fail`)

Validation command:

```bash
uv run python scripts/validate_attachment_recall_evidence.py --version v0.4.1rc4
```
