"""Feature and Data Drift Monitoring Engine (PSI & KS-Test)."""

import logging
from typing import Dict, Tuple
import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def calculate_psi(baseline: np.ndarray, current: np.ndarray, num_bins: int = 10) -> float:
    """Calculates Population Stability Index (PSI) between baseline and current feature distributions."""
    baseline = np.asarray(baseline[~np.isnan(baseline)])
    current = np.asarray(current[~np.isnan(current)])

    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    # Quantile binning based on baseline distribution
    quantiles = np.linspace(0, 100, num_bins + 1)
    bins = np.percentile(baseline, quantiles)
    bins = np.unique(bins) # remove duplicate bin edges

    if len(bins) < 2:
        return 0.0

    # Ensure min/max bounds include full data range
    bins[0] = min(baseline.min(), current.min()) - 1e-5
    bins[-1] = max(baseline.max(), current.max()) + 1e-5

    baseline_counts, _ = np.histogram(baseline, bins=bins)
    current_counts, _ = np.histogram(current, bins=bins)

    # Convert to proportions with zero-smoothing
    P = np.where(baseline_counts == 0, 1e-4, baseline_counts) / len(baseline)
    Q = np.where(current_counts == 0, 1e-4, current_counts) / len(current)

    psi_value = np.sum((P - Q) * np.log(P / Q))
    return float(np.round(psi_value, 4))


def calculate_feature_drift(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    numerical_features: list = None
) -> pd.DataFrame:
    """Evaluates Kolmogorov-Smirnov test and PSI across feature distributions to detect data drift.
    
    Returns:
        DataFrame summarizing feature drift metrics, PSI scores, KS p-values, and alert levels.
    """
    if numerical_features is None:
        numerical_features = baseline_df.select_dtypes(include=[np.number]).columns.tolist()

    drift_report = []

    for feature in numerical_features:
        if feature not in baseline_df.columns or feature not in current_df.columns:
            continue

        base_vals = baseline_df[feature].dropna().values
        curr_vals = current_df[feature].dropna().values

        if len(base_vals) < 5 or len(curr_vals) < 5:
            continue

        # 1. Kolmogorov-Smirnov 2-sample test
        ks_stat, p_value = stats.ks_2samp(base_vals, curr_vals)

        # 2. Population Stability Index (PSI)
        psi = calculate_psi(base_vals, curr_vals)

        # Classify drift alert level
        if psi >= 0.25 or p_value < 0.01:
            alert_level = "HIGH DRIFT (ALERT)"
        elif psi >= 0.10 or p_value < 0.05:
            alert_level = "MODERATE DRIFT (WARNING)"
        else:
            alert_level = "STABLE (NO DRIFT)"

        drift_report.append({
            "feature": feature,
            "psi_score": psi,
            "ks_statistic": round(ks_stat, 4),
            "p_value": round(p_value, 5),
            "baseline_mean": round(float(np.mean(base_vals)), 2),
            "current_mean": round(float(np.mean(curr_vals)), 2),
            "alert_level": alert_level,
        })

    report_df = pd.DataFrame(drift_report)
    if not report_df.empty:
        report_df.sort_values(by="psi_score", ascending=False, inplace=True)
        high_drift_count = len(report_df[report_df["alert_level"].str.contains("HIGH")])
        logger.info("Drift Audit Completed. Evaluated %d features. High Drift Alerts: %d", len(report_df), high_drift_count)

    return report_df
