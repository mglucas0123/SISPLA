import os
import sys
import re

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

app = create_app()
app.testing = True

with app.test_client() as client:
    resp = client.get('/avaliacao/funcionarios/avaliar')
    html = resp.get_data(as_text=True)
    if resp.status_code == 302 and '/login' in resp.headers.get('Location', ''):
        login_get = client.get('/login')
        login_html = login_get.get_data(as_text=True)
        m_login = re.search(r'name="csrf_token" value="([^"]+)"', login_html)
        login_token = m_login.group(1) if m_login else None
        login_data = {
            'csrf_token': login_token,
            'username': 'admin',
            'password': 'admin'
        }
        client.post('/login', data=login_data, follow_redirects=True)
        resp = client.get('/avaliacao/funcionarios/avaliar')
        html = resp.get_data(as_text=True)

    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    token = m.group(1) if m else None

    options = re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', html)
    user_id = options[0][0] if options else None
    print('CSRF token:', bool(token), 'user_id:', user_id)

    form = {
        'csrf_token': token,
        'evaluated_id': user_id,
        'month_reference': '2025-11',
        'evaluation_type': 'experiencia_90',
        'form_action': 'to_step2'
    }
    resp2 = client.post('/avaliacao/funcionarios/avaliar', data=form, follow_redirects=True)
    print('POST to_step2 status:', resp2.status_code)
    txt = resp2.get_data(as_text=True)
    if 'Critérios Qualitativos' in txt:
        print('Step2 present for experiencia_90')
    else:
        print('Step2 not present, snippet:\n', txt[:1000])

    # Now try to submit to step3 with minimal required fields for 90 days
    # collect csrf from resp2
    m2 = re.search(r'name="csrf_token" value="([^"]+)"', txt)
    token2 = m2.group(1) if m2 else token
    payload = {
        'csrf_token': token2,
        'evaluated_id': user_id,
        'month_reference': '2025-11',
        'evaluation_type': 'experiencia_90',
        'form_action': 'to_step3',
        'comm_verbal_90': '3',
        'comm_written_90': '3',
        'comm_collab_90': '3',
        'development_notes_90': 'ok',
        'post_experience_plan_90': 'plan',
        'approval_status_90': 'approved'
    }
    resp3 = client.post('/avaliacao/funcionarios/avaliar', data=payload, follow_redirects=True)
    print('POST to_step3 status:', resp3.status_code)
    txt3 = resp3.get_data(as_text=True)
    if 'Nota Final' in txt3:
        print('Step3 rendered for experiencia_90')
    else:
        print('Step3 not rendered, snippet:\n', txt3[:1000])
