import pytest
from cortia.analytics.baseline import summarize, compare

def test_baseline_minimum_independent_sessions():
    with pytest.raises(ValueError):
        summarize([{'id':'one', 'features':{'relative_alpha':.5}}]*3)

def test_baseline_statistics_and_zero_variance():
    rows = [{'id':str(i), 'features':{'relative_alpha':x, 'relative_theta':.2}} for i,x in enumerate([.4,.5,.6])]
    result = summarize(rows)
    assert result['relative_alpha']['mean'] == pytest.approx(.5)
    assert result['relative_alpha']['std'] == pytest.approx(.1)
    assert result['relative_theta']['std'] == 0
    differences = compare({'relative_alpha':.9, 'relative_theta':.2}, result)
    assert differences['relative_alpha']['flagged']
    assert differences['relative_theta']['z_score'] is None
