"""Job-level metrics aggregation helpers."""

from typing import Any

from ..models import EmailAnalysisResult


class JobMetricsCollector:
    """Aggregate job metrics from per-mail analysis results."""

    def build_job_metric(
        self,
        *,
        job_name: str,
        results: list[EmailAnalysisResult],
        batch_flush_enabled: bool,
    ) -> dict[str, Any]:
        """Build one job-level metric payload."""
        total_mail_ms = sum(
            float(result.metrics.get("mail_elapsed_ms", 0.0))
            for result in results
            if isinstance(result.metrics, dict)
        )
        llm_call_count = sum(
            int(result.metrics.get("llm_call_count", 0))
            for result in results
            if isinstance(result.metrics, dict)
        )
        llm_elapsed_ms = sum(
            float(result.metrics.get("llm_elapsed_ms", 0.0))
            for result in results
            if isinstance(result.metrics, dict)
        )
        job_plugin_status_distribution = {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "retriable_failed": 0,
        }
        for result in results:
            if not isinstance(result.metrics, dict):
                continue
            distribution = result.metrics.get("plugin_status_distribution", {})
            if not isinstance(distribution, dict):
                continue
            for key in job_plugin_status_distribution:
                job_plugin_status_distribution[key] += int(distribution.get(key, 0))

        return {
            "job_name": job_name,
            "mail_count": len(results),
            "mail_elapsed_ms": round(total_mail_ms, 2),
            "llm_call_count": llm_call_count,
            "llm_elapsed_ms": round(llm_elapsed_ms, 2),
            "plugin_status_distribution": job_plugin_status_distribution,
            "batch_flush_enabled": batch_flush_enabled,
        }
