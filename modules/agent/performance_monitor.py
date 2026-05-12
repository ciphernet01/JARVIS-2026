"""
Phase 3: Performance Monitoring

Tracks latency, throughput, and error rates for the voice system.
Useful for optimization and diagnostics.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    operation: str
    duration_ms: float
    timestamp: str
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """
    Monitors and aggregates performance metrics for:
    - Voice recognition latency
    - Assistant response latency
    - TTS latency
    - End-to-end latency
    - Error rates
    """

    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self._metrics: List[PerformanceMetric] = []
        self._lock = threading.RLock()
        self._operation_start_times: Dict[str, float] = {}

    def start_operation(self, operation_id: str) -> None:
        """Mark operation start."""
        self._operation_start_times[operation_id] = time.time()

    def end_operation(
        self,
        operation_id: str,
        operation_name: str,
        success: bool = True,
        metadata: Optional[Dict] = None,
    ) -> Optional[PerformanceMetric]:
        """Record operation completion."""
        start_time = self._operation_start_times.pop(operation_id, None)
        if start_time is None:
            logger.warning(f"End operation called without start: {operation_id}")
            return None

        duration_ms = (time.time() - start_time) * 1000

        with self._lock:
            metric = PerformanceMetric(
                operation=operation_name,
                duration_ms=round(duration_ms, 2),
                timestamp=datetime.now().isoformat(),
                success=success,
                metadata=metadata or {},
            )

            self._metrics.append(metric)

            # Keep only recent metrics
            if len(self._metrics) > self.history_size:
                self._metrics = self._metrics[-self.history_size :]

            logger.debug(
                f"[PERF] {operation_name}: {duration_ms:.1f}ms (success={success})"
            )
            return metric

    def get_metrics(
        self,
        operation: Optional[str] = None,
        num_metrics: int = 100,
    ) -> List[PerformanceMetric]:
        """Get recent metrics (snapshot)."""
        with self._lock:
            metrics = self._metrics.copy()

        if operation:
            metrics = [m for m in metrics if m.operation == operation]

        return metrics[-num_metrics:] if len(metrics) > num_metrics else metrics

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated statistics."""
        metrics = self.get_metrics(operation)
        if not metrics:
            return {}

        durations = [m.duration_ms for m in metrics]
        successful = [m for m in metrics if m.success]
        
        # Calculate p95 - always return at least p95
        sorted_durations = sorted(durations)
        p95_index = max(1, int(len(durations) * 0.95))
        p95_value = sorted_durations[p95_index - 1] if p95_index <= len(durations) else durations[-1]

        return {
            "count": len(metrics),
            "success_rate": round(len(successful) / len(metrics), 3),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "min_duration_ms": round(min(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "p95_duration_ms": round(p95_value, 2),
        }

    def get_operation_names(self) -> List[str]:
        """Get list of all tracked operations."""
        with self._lock:
            names = set(m.operation for m in self._metrics)
        return sorted(list(names))

    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()
            self._operation_start_times.clear()
        logger.info("[PERF] Metrics cleared")

    def __len__(self) -> int:
        """Get number of recorded metrics."""
        with self._lock:
            return len(self._metrics)


# Singleton instance
_instance = None
_lock = threading.Lock()


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create performance monitor singleton."""
    global _instance

    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PerformanceMonitor()

    return _instance
