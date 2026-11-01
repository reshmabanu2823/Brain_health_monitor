from cortia.analytics.anomalies import quality_events, deviation_events

def test_quality_and_gap_categories_are_separate():
    events=quality_events({'usable':False,'reasons':['missing_samples','clipping','flatline']})
    assert {e['category'] for e in events}=={'acquisition_gap','recording_artifact','poor_signal_quality'}
    assert all(e['details']['explanation'] for e in events)

def test_baseline_pattern_detection_is_explanatory():
    assert deviation_events({'available':False})==[]
    changes={'available':True,'included_in_baseline':False,'baseline_id':'baseline',
             'deviations':{'relative_alpha':{'flagged':True,'z_score':4}}}
    result=deviation_events(changes)
    assert result[0]['category']=='baseline_deviation'
    changes['included_in_baseline']=True
    assert deviation_events(changes)==[]
