"""Evidence-only language; optional AI selects allowed statements, never writes findings."""
import hashlib
import json
import httpx

def evidence(session, baseline):
    result = []
    def add(key,text):
        result.append({'id':key,'text':text})
    valid = session['valid_windows']
    invalid = session['invalid_windows']
    if not valid:
        add('quality','No usable eight-second EEG windows are available. Brainwave interpretation is unavailable.')
    else:
        add('quality',f'This recording contains {valid} usable and {invalid} rejected eight-second windows under exploratory quality checks.')
        features = session['features']
        bands = {k.removeprefix('relative_'):v for k,v in features.items() if k.startswith('relative_')}
        if bands:
            dominant = max(bands,key=bands.get)
            add('prominent',f'{dominant.title()} has the largest mean relative power: {bands[dominant]*100:.1f}% of retained 0.5–29.5 Hz power.')
        for band,value in bands.items():
            add('band_'+band,f'Mean {band} relative band power is {value*100:.1f}%.')
    if session['missing_samples']:
        add('gaps',f'{session["missing_samples"]} missing samples were detected. Affected windows are excluded from feature interpretation.')
    if baseline and baseline.get('available'):
        if baseline['included_in_baseline']:
            add('cohort','This session contributes to the selected baseline; comparison is in-sample, not independent change detection.')
        for name,change in baseline['deviations'].items():
            if change['flagged']:
                add('deviation_'+name,f'{name.replace("_"," ")} differs by {change["z_score"]:.2f} baseline standard deviations. This is an exploratory statistical flag.')
    else:
        add('baseline','No matching personal baseline is available. Independent change detection requires sufficient comparable recordings.')
    add('limits','Single-channel EEG and these ratios cannot establish attention, intelligence, anxiety, depression or a neurological diagnosis.')
    return result


def select_statements(payload, statements):
    if not isinstance(payload,dict) or set(payload) != {'statement_ids'}:
        raise ValueError('AI output must contain statement_ids only')
    selected = payload['statement_ids']
    allowed = {s['id']:s['text'] for s in statements}
    if not isinstance(selected,list) or not 1 <= len(selected) <= len(allowed) or any(not isinstance(k,str) or k not in allowed for k in selected) or len(set(selected)) != len(selected):
        raise ValueError('AI selected unsupported statements')
    # Always preserve quality and limitations, irrespective of model preference.
    ids = list(dict.fromkeys(['quality',*selected,'limits']))
    return [allowed[k] for k in ids if k in allowed]


def explain(session, baseline, settings, use_ai=False):
    statements = evidence(session,baseline)
    digest = hashlib.sha256(json.dumps({'session':session,'baseline':baseline},sort_keys=True,allow_nan=False).encode()).hexdigest()
    if not use_ai:
        return dict(kind='evidence_summary',provider='backend_templates',ai_generated=False,statements=[s['text'] for s in statements],evidence_digest=digest)
    if not settings.ai_endpoint or not settings.ai_model:
        raise ValueError('External AI is not configured. Evidence summary remains available.')
    # Curated statements contain no names, files, raw EEG or MRI images.
    response = httpx.post(settings.ai_endpoint,headers={'Authorization':f'Bearer {settings.ai_key}'},timeout=25,
        json={'model':settings.ai_model,'temperature':0,'max_tokens':300,
              'messages':[{'role':'system','content':'Select the most useful statement IDs. Return JSON only: {"statement_ids":["id"]}. Never add text or measurements.'},
                          {'role':'user','content':json.dumps(statements)}],
              'response_format':{'type':'json_object'}})
    response.raise_for_status()
    if len(response.content) > 65536:
        raise ValueError('AI response exceeds limit')
    payload = json.loads(response.json()['choices'][0]['message']['content'])
    text = select_statements(payload,statements)
    return dict(kind='ai_assisted_evidence_selection',provider=settings.ai_model,ai_generated=True,statements=text,evidence_digest=digest)
