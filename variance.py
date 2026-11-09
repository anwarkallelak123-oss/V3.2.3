"""Pre-TOST comparison of population variances using Brown–Forsythe."""
import numpy as np
from scipy.stats import levene


VARIANCE_ALPHA = .05
VARIANCE_METHOD = 'Brown–Forsythe (median-centered Levene), alpha = 0.05.'
VARIANCE_INTERPRETATION = 'A non-significant result provides no evidence of unequal variances. TOST uses pooled variance for non-significant results and Welch for significant or unavailable results.'


def variance_checks(selection, normalized, unresolved):
    rows = {}
    for pair in selection:
        ref, test = pair['reference'], pair['test']
        for param in pair['parameters']:
            samples = [np.asarray(normalized[machine][param], dtype=float) for machine in (ref, test)]
            ref_values, test_values = [sample[np.isfinite(sample)] for sample in samples]
            ref_n, test_n = len(ref_values), len(test_values)
            row = {
                'ET': pair['et'], 'Reference': ref, 'Test': test, 'Parameter': param,
                'N ref': ref_n, 'N test': test_n,
                'SD ref': float(np.std(ref_values, ddof=1)) if ref_n >= 2 else None,
                'SD test': float(np.std(test_values, ddof=1)) if test_n >= 2 else None,
                'Statistic': None, 'p-value': None, 'Assessment': 'Unavailable', 'TOST model': 'Welch', 'Note': '',
            }
            rows[pair['et'], param] = row
            if {(ref, param), (test, param)} & unresolved:
                row['Note'] = 'Exclusion rationale required.'
                continue
            if min(ref_n, test_n) < 3:
                row['Note'] = 'At least 3 usable observations per equipment are required for this check.'
                continue
            # Levene's denominator is zero if neither group's absolute
            # deviations from its median vary, including constant samples.
            ref_deviations = np.abs(ref_values - np.median(ref_values))
            test_deviations = np.abs(test_values - np.median(test_values))
            if np.ptp(ref_deviations) == 0 and np.ptp(test_deviations) == 0:
                row['Note'] = 'The absolute deviations have zero within-group variance.'
                continue
            statistic, p = levene(ref_values, test_values, center='median')
            if not np.isfinite(statistic) or not np.isfinite(p):
                row['Note'] = 'The variance test did not return a finite result.'
                continue
            row.update({
                'Statistic': float(statistic), 'p-value': float(p),
                'TOST model': 'Welch' if p <= VARIANCE_ALPHA else 'Pooled',
                'Assessment': 'Evidence of unequal variances' if p <= VARIANCE_ALPHA
                else 'No evidence of unequal variances',
            })
    return rows
