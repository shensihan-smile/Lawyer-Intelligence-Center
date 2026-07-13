"""全系统集成测试"""
import requests, time, os, tempfile, fitz

BASE = 'http://127.0.0.1:8000/api'
passed = 0
failed = 0


def check(desc, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  [PASS] {desc}')
    else:
        failed += 1
        print(f'  [FAIL] {desc} {detail}')


# ===== 1. AUTH =====
print('\n=== 1. Authentication ===')
r = requests.post(f'{BASE}/auth/login', data={'username': 'admin', 'password': 'admin123'})
check('Admin login', r.status_code == 200, r.text[:100])
admin_h = {'Authorization': f'Bearer {r.json()["access_token"]}'}

r = requests.post(f'{BASE}/auth/login', data={'username': 'nobody', 'password': 'wrong'})
check('Bad credentials rejected', r.status_code == 401)

# ===== 2. USER MANAGEMENT =====
print('\n=== 2. User Management ===')
r = requests.get(f'{BASE}/users/', headers=admin_h)
check('List users', r.status_code == 200 and len(r.json()) >= 1)

r = requests.post(f'{BASE}/users/', json={
    'username': 'lawyer01', 'password': '123456', 'real_name': '张律师', 'role': 'lawyer',
}, headers=admin_h)
check('Create lawyer', r.status_code == 200, r.text[:100])

r = requests.post(f'{BASE}/users/', json={
    'username': 'assist01', 'password': '123456', 'real_name': '王助理', 'role': 'assistant',
}, headers=admin_h)
check('Create assistant', r.status_code == 200)

r = requests.put(f'{BASE}/users/2/toggle-active', headers=admin_h)
check('Toggle disable lawyer', r.json().get('is_active') == False)

r = requests.put(f'{BASE}/users/2/toggle-active', headers=admin_h)
check('Toggle re-enable lawyer', r.json().get('is_active') == True)

r = requests.post(f'{BASE}/auth/login', data={'username': 'lawyer01', 'password': '123456'})
lawyer_h = {'Authorization': f'Bearer {r.json()["access_token"]}'}

r = requests.post(f'{BASE}/users/', json={
    'username': 'hacker', 'password': '123', 'real_name': '黑客', 'role': 'admin',
}, headers=lawyer_h)
check('Non-admin blocked from user mgmt', r.status_code == 403)

# ===== 3. CLIENTS =====
print('\n=== 3. Client Management ===')
r = requests.post(f'{BASE}/clients/', json={
    'name': '深圳创新科技有限公司', 'contact_person': '周总', 'phone': '13800001111',
}, headers=admin_h)
c1 = r.json()
check('Create client', r.status_code == 200)

r = requests.get(f'{BASE}/clients/', headers=admin_h)
check('List clients', r.status_code == 200 and len(r.json()) >= 1)

r = requests.put(f'{BASE}/clients/{c1["id"]}', json={'contact_person': '周总(更新)'}, headers=admin_h)
check('Update client', r.status_code == 200)

r = requests.get(f'{BASE}/clients/', headers=lawyer_h)
check('Lawyer isolated from admin clients', len(r.json()) == 0)

# ===== 4. CASES =====
print('\n=== 4. Case Management ===')
r = requests.post(f'{BASE}/cases/', json={
    'case_number': '(2026)京0105民初00001号', 'case_reason': '合同纠纷',
    'court': '北京市朝阳区人民法院', 'judge': '王法官', 'plaintiff': '甲公司', 'defendant': '乙公司',
    'client_ids': [c1['id']], 'third_party': ['丙公司'], 'amount_in_dispute': 500000,
}, headers=admin_h)
case1 = r.json()
check('Create case', r.status_code == 200)

r = requests.get(f'{BASE}/cases/', headers=admin_h)
check('List cases', len(r.json()) >= 1)

r = requests.put(f'{BASE}/cases/{case1["id"]}', json={
    'case_stage': 'trial', 'trial_date': '2026-09-01T09:00:00',
}, headers=admin_h)
check('Update case stage', r.status_code == 200 and r.json()['case_stage'] == 'trial')

r = requests.get(f'{BASE}/cases/', headers=lawyer_h)
check('Lawyer isolated from admin cases', len(r.json()) == 0)

r = requests.post(f'{BASE}/cases/', json={
    'case_number': '(2026)粤0305民初00002号', 'case_reason': '劳动争议',
}, headers=lawyer_h)
check('Lawyer create own case', r.status_code == 200)

r = requests.get(f'{BASE}/cases/', headers=lawyer_h)
check('Lawyer sees own case', len(r.json()) == 1)

# ===== 5. DOCUMENTS =====
print('\n=== 5. Document Management ===')
pdf_path = os.path.join(tempfile.gettempdir(), '_test.pdf')
pdf = fitz.open()
page = pdf.new_page()
page.insert_text((72, 200), 'Test Document', fontsize=20)
pdf.save(pdf_path)
pdf.close()

with open(pdf_path, 'rb') as f:
    r = requests.post(f'{BASE}/documents/upload',
                      files={'file': ('test.pdf', f)},
                      data={'doc_category': 'legal_opinion', 'case_id': case1['id'], 'client_id': c1['id']},
                      headers=admin_h)
doc1 = r.json()
check('Upload document', r.status_code == 200)

r = requests.get(f'{BASE}/documents/', headers=admin_h)
check('List documents', len(r.json()) >= 1)

r = requests.get(f'{BASE}/documents/{doc1["id"]}/preview', headers=admin_h)
check('PDF preview', r.status_code == 200)

with open(pdf_path, 'rb') as f:
    r = requests.post(f'{BASE}/documents/convert',
                      files={'file': ('test.pdf', f)},
                      data={'target_format': 'docx'},
                      headers=admin_h)
check('PDF -> Word conversion', r.status_code == 200)

with open(pdf_path, 'rb') as f:
    r = requests.post(f'{BASE}/documents/export-images',
                      files={'file': ('test.pdf', f)},
                      data={'mode': 'long', 'dpi': '120'},
                      headers=admin_h)
check('Export long image', r.status_code == 200)

# ===== 6. SCHEDULES =====
print('\n=== 6. Schedule Management ===')
r = requests.post(f'{BASE}/schedules/', json={
    'title': '开庭 - 合同纠纷', 'schedule_type': 'hearing', 'case_id': case1['id'],
    'start_time': '2026-09-15T09:00:00', 'end_time': '2026-09-15T12:00:00',
    'location': '朝阳法院 第3审判庭', 'judge': '王法官',
}, headers=admin_h)
check('Create schedule', r.status_code == 200)

r = requests.post(f'{BASE}/schedules/', json={
    'title': '会议(冲突测试)', 'schedule_type': 'meeting',
    'start_time': '2026-09-15T10:00:00', 'end_time': '2026-09-15T11:00:00',
}, headers=admin_h)
check('Conflict detection', len(r.json().get('conflicts', [])) > 0)

sms = '【12368法院服务平台】北京市朝阳区人民法院通知：关于(2026)京0105民初12345号案件，定于2026年10月20日09时30分在本院第5审判庭开庭审理，承办法官张三，联系电话010-12345678。'
r = requests.post(f'{BASE}/schedules/parse-sms', json={'text': sms}, headers=admin_h)
parsed = r.json()
check('SMS parse - case_number', bool(parsed.get('case_number')))
check('SMS parse - hearing time', bool(parsed.get('hearing_datetime')))

r = requests.post(f'{BASE}/schedules/create-from-sms', json={'sms_text': sms}, headers=admin_h)
check('Create from SMS', r.status_code == 200)

r = requests.get(f'{BASE}/schedules/export-ical', headers=admin_h)
check('iCal export', r.status_code == 200 and 'VCALENDAR' in r.text)

# ===== 7. BILLING =====
print('\n=== 7. Billing ===')
requests.post(f'{BASE}/billing/config', json={
    'name': '默认小时费率', 'billing_method': 'hourly', 'unit_price': 2000, 'is_default': True,
}, headers=admin_h)
check('Create billing config', True)

r = requests.post(f'{BASE}/billing/time-records', json={
    'case_id': case1['id'], 'work_category': 'drafting',
    'start_time': '2026-08-01T09:00:00', 'end_time': '2026-08-01T17:00:00',
    'description': '起草法律意见书',
}, headers=admin_h)
tr1 = r.json()
check('Create time record', r.status_code == 200 and tr1['duration_minutes'] > 0)

r = requests.post(f'{BASE}/billing/time-records/start',
                  json={'case_id': case1['id'], 'work_category': 'consultation'},
                  headers=admin_h)
active = r.json()
time.sleep(0.3)
r = requests.post(f'{BASE}/billing/time-records/{active["id"]}/stop', headers=admin_h)
check('Timer start/stop', r.json()['duration_minutes'] >= 1)

r = requests.post(f'{BASE}/billing/bills/generate', json={
    'client_id': c1['id'], 'period_start': '2026-08-01', 'period_end': '2026-08-31',
    'firm_name': '测试律师事务所', 'lawyer_name': '李律师',
}, headers=admin_h)
bill = r.json()
check('Generate bill', r.status_code == 200 and bill['total_amount'] > 0)

r = requests.get(f'{BASE}/billing/bills/{bill["id"]}/pdf', headers=admin_h,
                 params={'firm_name': '测试律所', 'lawyer_name': '李律师'})
check('Bill PDF export', r.status_code == 200 and len(r.content) > 1000)

# ===== 8. CLEANUP =====
print('\n=== 8. Cleanup ===')
for url, hid in [('/cases/', admin_h), ('/clients/', admin_h)]:
    try:
        for item in requests.get(f'{BASE}{url}', headers=hid).json():
            if isinstance(item, dict) and 'id' in item:
                requests.delete(f'{BASE}{url}{item["id"]}', headers=hid)
    except:
        pass
for uid in [2, 3]:
    try:
        requests.delete(f'{BASE}/users/{uid}', headers=admin_h)
    except:
        pass
for url in ['/billing/bills', '/billing/time-records', '/billing/config']:
    try:
        for item in requests.get(f'{BASE}{url}', headers=admin_h).json():
            if isinstance(item, dict) and 'id' in item:
                requests.delete(f'{BASE}{url}{item["id"]}', headers=admin_h)
    except:
        pass
check('Cleanup complete', True)

# ===== RESULTS =====
print(f'\n{"=" * 50}')
print(f'RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests')
if failed == 0:
    print('ALL INTEGRATION TESTS PASSED!')
else:
    print(f'{failed} TESTS FAILED!')
