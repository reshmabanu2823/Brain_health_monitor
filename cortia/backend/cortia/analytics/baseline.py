"""Each independent recording contributes once; frozen cohorts avoid silent drift."""
import numpy as np

def summarize(rows):
    if len({row['id'] for row in rows}) < 3 or len({row['id'] for row in rows}) != len(rows):
        raise ValueError('At least three distinct, completed, comparable sessions required')
    common = set.intersection(*(set(r['features']) for r in rows))
    if not common:
        raise ValueError('No shared valid features')
    result = {}
    for name in sorted(common):
        values = np.asarray([r['features'][name] for r in rows], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError('Non-finite baseline feature')
        result[name] = dict(mean=float(values.mean()), median=float(np.median(values)), std=0.0 if np.ptp(values) == 0 else float(values.std(ddof=1)), n=len(rows))
    return result


def compare(features, statistics):
    result = {}
    for name, value in features.items():
        if name not in statistics:
            continue
        stats = statistics[name]
        z = (value-stats['mean'])/stats['std'] if stats['std'] > 1e-12 else None
        result[name] = dict(value=value, baseline_mean=stats['mean'], difference=value-stats['mean'], z_score=z,
                            flagged=z is not None and abs(z) >= 3,
                            explanation='Exploratory ≥3 SD deviation; not a clinical threshold.' if z is not None else 'Baseline variance too small for a stable z-score.')
    return result
