import pytest
from cortia.services.explanations import evidence, select_statements


def test_no_data_explanations_never_invent_metrics():
    statements = evidence({'valid_windows':0,'invalid_windows':0,'features':{},'missing_samples':0},None)
    assert any('No usable' in s['text'] for s in statements)
    assert not any('alpha power is' in s['text'] for s in statements)


def test_ai_cannot_supply_text_or_unknown_statement():
    statements = [{'id':'quality','text':'No usable windows.'}]
    with pytest.raises(ValueError):
        select_statements({'statement_ids':['diagnosis']}, statements)
    with pytest.raises(ValueError):
        select_statements({'statement_ids':['quality'], 'text':'Invented diagnosis'},statements)
    assert select_statements({'statement_ids':['quality']},statements) == ['No usable windows.']
