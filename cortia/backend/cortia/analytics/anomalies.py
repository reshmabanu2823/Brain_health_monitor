"""Transparent event detection; categories never represent neurological diagnoses."""
EXPLANATIONS = {
    'missing_samples': ('acquisition_gap','Counter loss or byte corruption interrupts this window. No interpolation is used for analysis.'),
    'clipping': ('recording_artifact','More than 1% of raw samples are at ADC rails; amplitude and spectral features are unreliable.'),
    'abrupt_step': ('recording_artifact','A large raw step exceeds the configured robust-difference threshold; movement or contact changes are possible.'),
    'flatline': ('poor_signal_quality','Raw variation is below the configured threshold or repeated samples dominate.'),
    'insufficient_power': ('poor_signal_quality','Retained-band power is too small for stable ratios.')
}

def quality_events(quality):
    return [dict(category=EXPLANATIONS.get(reason,('poor_signal_quality','Window failed a configured quality check.'))[0],
                 details={'reason':reason,'explanation':EXPLANATIONS.get(reason,('','Window failed a configured quality check.'))[1],
                          'method':'exploratory_engineering_threshold'}) for reason in quality['reasons']]


def deviation_events(comparison):
    if not comparison.get('available') or comparison.get('included_in_baseline'):
        return []
    features = {k:v for k,v in comparison['deviations'].items() if v['flagged']}
    if not features:
        return []
    return [dict(category='baseline_deviation',details={'baseline_id':comparison['baseline_id'],'features':features,
                  'explanation':'One or more session features differ by at least three baseline sample standard deviations. Exploratory pattern flag, not diagnosis or validated clinical change.'})]
