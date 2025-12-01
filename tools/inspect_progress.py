import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.models import db, User

app = create_app()
app.testing = True

with app.test_client() as c:
    # initial GET -> login redirect
    r = c.get('/avaliacao/funcionarios/avaliar')
    if r.status_code == 302:
        # get login page
        login = c.get('/login')
        import re
        m = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', login.data.decode('utf-8'))
        token = m.group(1) if m else ''
        # perform login with admin/admin
        payload = {'username':'admin','password':'admin','csrf_token':token}
        r2 = c.post('/login', data=payload)
        r = c.get('/avaliacao/funcionarios/avaliar')

    # parse initial page
    import re
    html = r.data.decode('utf-8')
    print('Initial progress HTML:')
    items = re.findall(r'<div class="progress-step\s*([^\"]*)"\s+data-step="(\d)"', html)
    print('progress-step items:', items)

    # submit step1 to go to step2
    # Extract CSRF and first user option via regex
    form_html = re.search(r'(<form[^>]*id="evaluationForm"[\s\S]*?</form>)', html)
    form_html = form_html.group(1) if form_html else html
    csrf_search = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', form_html)
    csrf = csrf_search.group(1) if csrf_search else ''
    opt = re.search(r'<select[^>]*id="evaluated_id"[\s\S]*?<option\s+value="([^"]+)"', form_html)
    first_user = opt.group(1) if opt else ''
    payload = {'csrf_token': csrf, 'evaluated_id': first_user, 'month_reference': '2025-11', 'evaluation_type': 'mensal', 'form_action': 'to_step2'}
    r_step2 = c.post('/avaliacao/funcionarios/avaliar', data=payload)
    html2 = r_step2.data.decode('utf-8')
    items2 = re.findall(r'<div class="progress-step\s*([^\"]*)"\s+data-step="(\d)"', html2)
    print('\nAfter to_step2 progress-step items:', items2)

    # simulate filling minimal required monthly fields and submit to step3
    # find token from html2 form via regex
    form2_match = re.search(r'(<form[^>]*id="evaluationForm"[\s\S]*?</form>)', html2)
    form2_html = form2_match.group(1) if form2_match else html2
    csrf2_search = re.search(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']', form2_html)
    csrf2 = csrf2_search.group(1) if csrf2_search else csrf
    payload2 = {'csrf_token': csrf2, 'evaluated_id': first_user, 'month_reference': '2025-11', 'evaluation_type': 'mensal', 'form_action': 'to_step3',
                'participation_score': '5', 'innovation_suggestions': 'suggest', 'participation_activities': 'acts', 'collaborator_goal': 'goal', 'development_points': 'dp', 'development_strategy': 'ds', 'other_analyses': 'oa'
               }
    r_step3 = c.post('/avaliacao/funcionarios/avaliar', data=payload2)
    html3 = r_step3.data.decode('utf-8')
    items3 = re.findall(r'<div class="progress-step\s*([^\"]*)"\s+data-step="(\d)"', html3)
    print('\nAfter to_step3 progress-step items:', items3)
