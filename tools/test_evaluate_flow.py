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
    # GET the form to obtain CSRF token and initial cookies
    resp = client.get('/avaliacao/funcionarios/avaliar')
    html = resp.get_data(as_text=True)
    print('Initial GET status code:', resp.status_code)
    # If redirected to login, perform login using default admin/admin
    if resp.status_code == 302 and '/login' in resp.headers.get('Location', ''):
        print('Not logged in; attempting login with default admin/admin')
        login_get = client.get('/login')
        login_html = login_get.get_data(as_text=True)
        m_login = re.search(r'name="csrf_token" value="([^\"]+)"', login_html)
        login_token = m_login.group(1) if m_login else None
        print('Login page token found:', bool(login_token))
        login_data = {
            'csrf_token': login_token,
            'username': 'admin',
            'password': 'admin'
        }
        resp_login = client.post('/login', data=login_data, follow_redirects=True)
        print('Login POST status:', resp_login.status_code)
        # Try to GET evaluation form again
        resp = client.get('/avaliacao/funcionarios/avaliar')
        html = resp.get_data(as_text=True)
    print('GET status code (final):', resp.status_code)
    print('Response snippet:\n', html[:1000])
    m = re.search(r'name="csrf_token" value="([^\"]+)"', html)
    token = m.group(1) if m else None
    print('Got CSRF token:', bool(token))

    # Ensure there's at least one other active user to select
    from app.models import db, User
    from werkzeug.security import generate_password_hash
    with app.app_context():
        existing = db.session.execute(db.select(User).filter_by(username='__test_user__')).scalar_one_or_none()
        if not existing:
            u = User(name='Test User', username='__test_user__', email='test@example.com', password=generate_password_hash('testpass'), profile='', is_active=True)
            db.session.add(u)
            db.session.commit()
            print('Created test user __test_user__')
        else:
            print('Test user already present')

    # Prepare form data for step1 -> to_step2
    form = {
        'csrf_token': token,
        'evaluated_id': '',
        'month_reference': '',
        'evaluation_type': 'mensal',
        'form_action': 'to_step2'
    }
    # First try with empty evaluated_id/month to see validation
    resp2 = client.post('/avaliacao/funcionarios/avaliar', data=form, follow_redirects=True)
    print('POST status code (empty fields):', resp2.status_code)
    if b'Por favor, selecione um colaborador' in resp2.data:
        print('Server-side validation for evaluated_id triggered')

    # Now post with values
    # Get a valid user id from page options
    options = re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', html)
    print('Found options:', options)
    user_id = options[0][0] if options else None
    if not user_id:
        print('No user options found, aborting test')
    else:
        form['evaluated_id'] = user_id
        form['month_reference'] = '2025-11'
        resp3 = client.post('/avaliacao/funcionarios/avaliar', data=form, follow_redirects=True)
        print('POST status code (with values):', resp3.status_code)
        # Check if the response contains elements from step2
        if b'Crit\xc3\xadrios Qualitativos' in resp3.data or b'Participa das Atividades' in resp3.data:
            print('Step 2 rendered successfully')
        else:
            print('Step 2 not rendered; response snippet:')
            print(resp3.get_data(as_text=True)[:800])
