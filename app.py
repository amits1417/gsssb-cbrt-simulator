import os
import json
import re
import datetime
from functools import wraps
import io
import qrcode
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, abort, send_file
import database as db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMS_DIR = os.path.join(BASE_DIR, 'exams')

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates')
)
app.secret_key = os.environ.get('SECRET_KEY', 'gsssb_cbrt_super_secret_key_2026_x89f21')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure directories exist safely (avoid crash on read-only serverless filesystems)
try:
    os.makedirs(os.path.join(BASE_DIR, 'static', 'css'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static', 'js'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'static', 'images'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'templates'), exist_ok=True)
except Exception:
    pass


# ----------------- Helper Decorators -----------------

def get_current_user():
    # Check session cookie or Authorization header
    token = session.get('session_token') or request.headers.get('X-Session-Token')
    if not token:
        return None
    return db.get_user_by_session(token)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            return redirect(url_for('auth_page', next=request.path))
        return f(*args, user=user, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user or not user.get('is_admin'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin privileges required', 'code': 'ADMIN_REQUIRED'}), 403
            return redirect(url_for('auth_page'))
        return f(*args, user=user, **kwargs)
    return decorated_function

# ----------------- Static Exam Files Helper -----------------

@app.route('/exams/<path:filename>')
def serve_exam_files(filename):
    # Free papers (PAPER-1 and PAPER-2) are open to all
    # Other papers check if the user is paid or admin
    is_free = filename.startswith('PAPER-1/') or filename.startswith('PAPER-2/') or filename == 'PAPER-1' or filename == 'PAPER-2'
    if not is_free and not filename.endswith('.png'):  # allow images or check user
        user = get_current_user()
        if not user or (not user.get('is_paid') and not user.get('is_admin')):
            abort(403)
    return send_from_directory(EXAMS_DIR, filename)

# ----------------- Page Routes -----------------

@app.route('/')
def index():
    user = get_current_user()
    settings = db.get_settings()
    return render_template('index.html', user=user, settings=settings)

@app.route('/login')
@app.route('/register')
@app.route('/auth')
def auth_page():
    user = get_current_user()
    if user:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/dashboard')
@login_required
def dashboard(user):
    settings = db.get_settings()
    stats = db.get_user_stats(user['id'])
    return render_template('dashboard.html', user=user, stats=stats, settings=settings)

@app.route('/leaderboard')
def leaderboard_page():
    user = get_current_user()
    leaderboard = db.get_leaderboard(100)
    return render_template('leaderboard.html', user=user, leaderboard=leaderboard)

@app.route('/pricing')
@app.route('/payment')
def payment_page():
    user = get_current_user()
    settings = db.get_settings()
    return render_template('payment.html', user=user, settings=settings)

@app.route('/api/qr-code')
def api_generate_qr_code():
    amount = request.args.get('amount', '299').strip()
    plan = request.args.get('plan', 'Mock Test Pass').strip()
    vpa = "amit109881.rzp@rxairtel"
    payee = "AMIT"
    
    # Dynamic UPI URI format with exact amount parameter (am=...)
    upi_uri = f"upi://pay?pa={vpa}&pn={payee}&am={amount}&cu=INR&tn=GSSSB CCE {plan}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e1b4b", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/exam/<paper_id>')
def exam_page(paper_id):
    user = get_current_user()
    is_free = paper_id in ['PAPER-1', 'PAPER-2']
    
    # If not free, must be logged in and paid
    if not is_free:
        if not user:
            return redirect(url_for('auth_page', next=request.path))
        if not user.get('is_paid') and not user.get('is_admin'):
            return redirect(url_for('payment_page', locked_paper=paper_id))
            
    return render_template('exam.html', user=user, paper_id=paper_id, is_free=is_free)

@app.route('/admin')
@admin_required
def admin_page(user):
    settings = db.get_settings()
    stats = db.get_admin_dashboard_stats()
    users = db.get_all_users_admin()
    payments = db.get_all_payments_admin()
    tickets = db.get_all_support_tickets_admin()
    return render_template('admin.html', user=user, settings=settings, stats=stats, users=users, payments=payments, tickets=tickets)

# ----------------- Auth API Endpoints -----------------

@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    
    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required.'}), 400
        
    if not phone or len(phone) < 10 or not phone.isdigit():
        return jsonify({'error': 'A valid 10-digit mobile number is compulsory.'}), 400
        
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400
        
    device_id = data.get('device_id')
    user, result = db.create_user(name, email, phone, password, device_id)
    if not user:
        return jsonify({'error': result}), 400
        
    session['session_token'] = result
    return jsonify({
        'success': True,
        'message': 'Account created successfully!',
        'user': user,
        'token': result
    })

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    device_info = data.get('device_info', request.headers.get('User-Agent', 'Web Browser'))
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400
        
    device_id = data.get('device_id')
    result = db.authenticate_user(email, password, device_id, device_info, ip_addr)
    
    if result['status'] == 'ERROR':
        return jsonify({'error': result['message']}), 401
        
    if result['status'] == 'NEEDS_OTP':
        return jsonify({
            'needs_otp': True,
            'email': result['email'],
            'message': result['message'],
            'dev_otp': result.get('dev_otp')
        }), 200
        
    session['session_token'] = result['token']
    return jsonify({
        'success': True,
        'message': 'Logged in successfully!',
        'user': result['user'],
        'token': result['token']
    })

@app.route('/api/auth/verify-otp', methods=['POST'])
def api_verify_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    otp = data.get('otp', '').strip()
    device_id = data.get('device_id')
    device_info = data.get('device_info', request.headers.get('User-Agent', 'Web Browser'))
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required.'}), 400
        
    result = db.verify_otp_and_login(email, otp, device_id, device_info, ip_addr)
    if result['status'] == 'ERROR':
        return jsonify({'error': result['message']}), 401
        
    session['session_token'] = result['token']
    return jsonify({
        'success': True,
        'message': 'Device authorized! Logged in successfully.',
        'user': result['user'],
        'token': result['token']
    })

@app.route('/api/auth/resend-otp', methods=['POST'])
def api_resend_otp():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    if not email:
        return jsonify({'error': 'Email is required.'}), 400
    result = db.resend_otp(email)
    if result['status'] == 'ERROR':
        return jsonify({'error': result['message']}), 401
    return jsonify({
        'success': True,
        'message': result['message'],
        'dev_otp': result.get('dev_otp')
    })

@app.route('/api/auth/request-device-reset', methods=['POST'])
def api_request_device_reset():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400
    result = db.request_device_reset_otp(email, password)
    if result['status'] == 'ERROR':
        return jsonify({'error': result['message']}), 400
    return jsonify({
        'success': True,
        'message': result['message'],
        'email': result['email'],
        'resets_used': result['resets_used'],
        'remaining_resets': result['remaining_resets'],
        'dev_otp': result.get('dev_otp')
    })

@app.route('/api/auth/confirm-device-reset', methods=['POST'])
def api_confirm_device_reset():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    otp = data.get('otp', '').strip()
    device_id = data.get('device_id')
    device_info = data.get('device_info', request.headers.get('User-Agent', 'New Device'))
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required.'}), 400
        
    result = db.confirm_device_reset(email, otp, device_id, device_info, ip_addr)
    if result['status'] == 'ERROR':
        return jsonify({'error': result['message']}), 400
        
    session['session_token'] = result['token']
    return jsonify({
        'success': True,
        'message': result['message'],
        'user': result['user'],
        'token': result['token']
    })

@app.route('/api/auth/google', methods=['POST'])
def api_google_auth():
    import base64
    data = request.get_json() or {}
    credential = data.get('credential')
    email = data.get('email')
    name = data.get('name')
    google_id = data.get('google_id')
    avatar_url = data.get('avatar_url')
    phone = data.get('phone')
    device_info = data.get('device_info', request.headers.get('User-Agent', 'Google Sign-In Device'))
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)

    # If Google JWT credential provided by Google Identity Services (GIS)
    if credential:
        try:
            parts = credential.split('.')
            if len(parts) >= 2:
                # Add padding if needed
                payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
                decoded_bytes = base64.urlsafe_b64decode(payload_b64)
                payload = json.loads(decoded_bytes.decode('utf-8'))
                email = payload.get('email')
                name = payload.get('name')
                google_id = payload.get('sub')
                avatar_url = payload.get('picture')
        except Exception as e:
            return jsonify({'error': 'Invalid Google token'}), 400

    if not email:
        return jsonify({'error': 'Google account email not found'}), 400

    user, token, is_new = db.google_auth_user(email, name, google_id, avatar_url, phone, device_info, ip_addr, data.get('device_id'))
    session['session_token'] = token

    needs_phone = not bool(user.get('phone') and len(user.get('phone')) >= 10)

    return jsonify({
        'success': True,
        'message': 'Google Sign-In successful!',
        'user': user,
        'token': token,
        'is_new': is_new,
        'needs_phone': needs_phone
    })

@app.route('/api/auth/update-phone', methods=['POST'])
@login_required
def api_update_phone(user):
    data = request.get_json() or {}
    phone = data.get('phone', '').strip()
    success, msg = db.update_user_phone(user['id'], phone)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'success': True, 'message': msg})

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({'logged_in': False}), 200
    return jsonify({'logged_in': True, 'user': user})

@app.route('/api/auth/heartbeat', methods=['POST'])
def api_heartbeat():
    token = session.get('session_token') or request.headers.get('X-Session-Token')
    device_id = request.headers.get('X-Device-Id') or (request.get_json() or {}).get('device_id')
    if not token:
        return jsonify({'status': 'invalid', 'error': 'No session token provided'}), 401
    user = db.get_user_by_session(token, device_id)
    if not user:
        # Session was revoked because user logged in from another device/browser!
        session.clear()
        return jsonify({
            'status': 'session_revoked',
            'error': 'You have been logged out because this account was logged in from another device.'
        }), 401
    return jsonify({'status': 'active', 'user_id': user['id'], 'is_paid': user['is_paid']})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    token = session.get('session_token') or request.headers.get('X-Session-Token')
    db.logout_user(token)
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

# ----------------- Exams API Endpoints -----------------

@app.route('/api/exams', methods=['GET'])
def api_get_exams():
    user = get_current_user()
    is_paid = bool(user and (user.get('is_paid') or user.get('is_admin')))
    user_attempts = db.get_user_exam_attempts_map(user['id']) if user else {}
    
    exams_list = []
    for i in range(1, 72):
        paper_id = f"PAPER-{i}"
        paper_name = f"Paper-{i} Combined Competitive Exam (Group A & B)"
        is_free = (i <= 2)
        is_locked = not is_free and not is_paid
        
        attempt_info = user_attempts.get(paper_id)
        is_completed = attempt_info is not None
        
        exam_item = {
            'id': paper_id,
            'number': i,
            'name': paper_name,
            'is_free': is_free,
            'is_locked': is_locked,
            'questions_count': 100,
            'duration_minutes': 60,
            'is_completed': is_completed
        }
        if is_completed:
            exam_item['best_score'] = attempt_info['best_score']
            exam_item['best_accuracy'] = attempt_info['best_accuracy']
            exam_item['attempts_count'] = attempt_info['attempts_count']
            
        exams_list.append(exam_item)
        
    return jsonify({'exams': exams_list, 'is_user_paid': is_paid, 'logged_in': bool(user)})

@app.route('/api/exams/<paper_id>/questions', methods=['GET'])
def api_get_exam_questions(paper_id):
    is_free = paper_id in ['PAPER-1', 'PAPER-2']
    user = get_current_user()
    
    if not is_free:
        if not user:
            return jsonify({'error': 'Please login to access this exam', 'code': 'AUTH_REQUIRED'}), 401
        if not user.get('is_paid') and not user.get('is_admin'):
            return jsonify({'error': 'Subscription required to unlock this exam', 'code': 'PAYWALL'}), 403
            
    questions_file = os.path.join(EXAMS_DIR, paper_id, 'questions.js')
    if not os.path.exists(questions_file):
        return jsonify({'error': 'Exam paper questions not found'}), 404
        
    with open(questions_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Extract JSON array from "window.examQuestions = [ ... ];"
    match = re.search(r'window\.examQuestions\s*=\s*(\[[\s\S]*\]);?', content)
    if not match:
        return jsonify({'error': 'Could not parse exam questions'}), 500
        
    questions_data = json.loads(match.group(1))
    return jsonify({
        'paper_id': paper_id,
        'total': len(questions_data),
        'questions': questions_data
    })

@app.route('/api/exams/submit', methods=['POST'])
def api_submit_exam():
    user = get_current_user()
    data = request.get_json() or {}
    
    paper_id = data.get('paper_id')
    user_answers = data.get('answers', {}) # dict of q_num -> selected_option (1-5)
    time_taken = int(data.get('time_taken', 0))
    
    if not paper_id:
        return jsonify({'error': 'paper_id is required'}), 400
        
    questions_file = os.path.join(EXAMS_DIR, paper_id, 'questions.js')
    if not os.path.exists(questions_file):
        return jsonify({'error': 'Exam paper not found'}), 404
        
    with open(questions_file, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'window\.examQuestions\s*=\s*(\[[\s\S]*\]);?', content)
    questions = json.loads(match.group(1))
    
    # Calculate score
    total_q = len(questions)
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    review_list = []
    
    for q in questions:
        q_num = str(q['number'])
        user_ans = user_answers.get(q_num) or user_answers.get(int(q_num))
        correct_ans = q.get('correct_option_index')
        
        status = 'unattempted'
        is_correct = False
        
        if user_ans is None or user_ans == 5 or user_ans == '5': # 5 is option E (Not Attempted)
            unattempted_count += 1
            status = 'unattempted'
        elif int(user_ans) == correct_ans:
            correct_count += 1
            is_correct = True
            status = 'correct'
        else:
            incorrect_count += 1
            status = 'incorrect'
            
        review_list.append({
            'number': q['number'],
            'id': q.get('id', ''),
            'english_prompt': q.get('english_prompt', ''),
            'gujarati_prompt_path': q.get('gujarati_prompt_path', ''),
            'options': q.get('options', []),
            'user_ans': user_ans,
            'correct_ans': correct_ans,
            'status': status,
            'is_correct': is_correct
        })
        
    # GSSSB CBRT Marking Scheme: +1.0 for Correct, -0.25 for Incorrect, 0 for Unattempted
    net_score = round(max(0.0, (correct_count * 1.0) - (incorrect_count * 0.25)), 2)

    attempted_total = correct_count + incorrect_count
    accuracy = round((correct_count / attempted_total * 100), 1) if attempted_total > 0 else 0.0
    
    attempt_id = None
    if user:
        attempt_id = db.save_test_attempt(
            user['id'], paper_id, total_q, correct_count, incorrect_count, 
            unattempted_count, net_score, time_taken, user_answers
        )
        
    return jsonify({
        'success': True,
        'attempt_id': attempt_id,
        'total_questions': total_q,
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
        'unattempted_count': unattempted_count,
        'net_score': net_score,
        'accuracy': accuracy,
        'time_taken': time_taken,
        'review': review_list
    })

# ----------------- Dashboard & Stats API -----------------

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats(user):
    stats = db.get_user_stats(user['id'])
    return jsonify({'success': True, 'stats': stats, 'user': user})

@app.route('/api/dashboard/attempt/<int:attempt_id>', methods=['GET'])
@login_required
def api_attempt_details(attempt_id, user):
    attempt = db.get_attempt_details(attempt_id, user['id'] if not user.get('is_admin') else None)
    if not attempt:
        return jsonify({'error': 'Attempt not found'}), 404
    return jsonify({'success': True, 'attempt': attempt})

# ----------------- Leaderboard API -----------------

@app.route('/api/leaderboard', methods=['GET'])
def api_leaderboard():
    limit = min(int(request.args.get('limit', 100)), 500)
    leaderboard = db.get_leaderboard(limit)
    user = get_current_user()
    user_rank_info = None
    if user:
        stats = db.get_user_stats(user['id'])
        user_rank_info = {
            'user_id': user['id'],
            'candidate_name': user['name'],
            'user_rank': stats.get('user_rank'),
            'avg_score': stats.get('avg_score'),
            'best_score': stats.get('best_score'),
            'total_tests': stats.get('total_tests'),
            'percentile': stats.get('percentile')
        }
    return jsonify({'leaderboard': leaderboard, 'user_rank_info': user_rank_info})

# ----------------- Payment API Endpoints -----------------

@app.route('/api/payment/details', methods=['GET'])
def api_payment_details():
    settings = db.get_settings()
    return jsonify({
        'price': settings.get('subscription_price', '300'),
        'upi_id': settings.get('upi_id', 'gsssbexams@upi'),
        'upi_name': settings.get('upi_name', 'GSSSB CBRT Mock Tests')
    })

@app.route('/api/payment/submit', methods=['POST'])
@login_required
def api_payment_submit(user):
    data = request.get_json() or {}
    utr_number = data.get('utr_number', '').strip()
    notes = data.get('notes', '').strip()
    amount = float(data.get('amount', 300.0))
    plan_name = data.get('plan_name', '1 Month Plan')
    
    if not utr_number or len(utr_number) < 6:
        return jsonify({'error': 'Please enter a valid UTR / Transaction ID (min 6 digits)'}), 400
        
    full_notes = f"{plan_name} | {notes}".strip(' |')
    payment_id = db.create_payment_request(user['id'], utr_number, amount, 'UPI', full_notes)
    
    # If auto-activation enabled in settings:
    settings = db.get_settings()
    if settings.get('allow_auto_activation') == '1':
        db.approve_payment(payment_id)
        return jsonify({
            'success': True,
            'auto_activated': True,
            'message': 'Payment verified and Subscription activated successfully!'
        })
        
    return jsonify({
        'success': True,
        'auto_activated': False,
        'message': 'Payment details submitted successfully! Your account will be activated within 15-30 minutes after verification.'
    })

# ----------------- Admin API Endpoints -----------------

@app.route('/api/admin/toggle-subscription', methods=['POST'])
@admin_required
def api_admin_toggle_sub(user):
    data = request.get_json() or {}
    target_user_id = data.get('user_id')
    is_paid = bool(data.get('is_paid'))
    if not target_user_id:
        return jsonify({'error': 'user_id is required'}), 400
    db.toggle_user_subscription(target_user_id, is_paid)
    return jsonify({'success': True, 'message': f'Subscription {"activated" if is_paid else "deactivated"} successfully!'})

@app.route('/api/admin/verify-payment', methods=['POST'])
@admin_required
def api_admin_verify_payment(user):
    data = request.get_json() or {}
    payment_id = data.get('payment_id')
    action = data.get('action') # 'approve' or 'reject'
    if not payment_id or action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid request'}), 400
    if action == 'approve':
        db.approve_payment(payment_id)
        return jsonify({'success': True, 'message': 'Payment approved & user unlocked!'})
    else:
        conn = db.get_db_connection()
        conn.execute('UPDATE payments SET status = "rejected" WHERE id = ?', (payment_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Payment rejected.'})

@app.route('/api/admin/settings', methods=['POST'])
@admin_required
def api_admin_update_settings(user):
    data = request.get_json() or {}
    for k, v in data.items():
        db.update_setting(k, str(v))
    return jsonify({'success': True, 'message': 'Settings updated successfully!'})

@app.route('/api/admin/delete-user', methods=['POST'])
@admin_required
def api_admin_delete_user(user):
    data = request.get_json() or {}
    target_id = data.get('user_id')
    if not target_id:
        return jsonify({'error': 'user_id is required'}), 400
    success, msg = db.delete_user(target_id, user['id'])
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'success': True, 'message': msg})

@app.route('/api/admin/reset-device', methods=['POST'])
@admin_required
def api_admin_reset_device(user):
    data = request.get_json() or {}
    target_id = data.get('user_id')
    if not target_id:
        return jsonify({'error': 'user_id is required'}), 400
    success, msg = db.reset_user_device(target_id)
    return jsonify({'success': True, 'message': msg})

@app.route('/api/admin/user/<int:user_id>', methods=['GET'])
@admin_required
def api_admin_user_details(user_id, user=None):
    details = db.get_user_full_details(user_id)
    if not details:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'success': True, 'user': details['user'], 'payments': details['payments'],
                   'attempts': details['attempts'], 'stats': details['stats']})

@app.route('/api/support/submit', methods=['POST'])
def api_submit_support():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    category = data.get('category', 'General Support').strip()
    message = data.get('message', '').strip()
    
    if not name or not email or not message:
        return jsonify({'error': 'Name, email, and message are required.'}), 400
        
    session_token = session.get('session_token')
    user = db.get_user_by_session(session_token) if session_token else None
    user_id = user['id'] if user else None
    
    success, msg = db.create_support_ticket(name, email, phone, category, message, user_id)
    return jsonify({'success': True, 'message': msg})

@app.route('/api/admin/support-tickets/<int:ticket_id>/status', methods=['POST'])
@admin_required
def api_admin_update_ticket_status(ticket_id, user=None):
    data = request.get_json() or {}
    new_status = data.get('status', 'resolved')
    db.update_support_ticket_status(ticket_id, new_status)
    return jsonify({'success': True, 'message': f'Ticket status updated to {new_status}.'})

@app.route('/api/admin/support-tickets/<int:ticket_id>/reply', methods=['POST'])
@admin_required
def api_admin_reply_ticket(ticket_id, user=None):
    data = request.get_json() or {}
    reply_msg = data.get('reply', '').strip()
    if not reply_msg:
        return jsonify({'error': 'Reply message cannot be empty.', 'success': False}), 400
    success, msg = db.reply_to_support_ticket(ticket_id, reply_msg)
    if not success:
        return jsonify({'error': msg, 'success': False}), 400
    return jsonify({'success': True, 'message': msg})

@app.route('/api/admin/support-tickets/<int:ticket_id>/delete', methods=['POST'])
@admin_required
def api_admin_delete_ticket(ticket_id, user=None):
    db.delete_support_ticket(ticket_id)
    return jsonify({'success': True, 'message': 'Support ticket deleted.'})

@app.route('/api/user/my-tickets', methods=['GET'])
def api_get_my_tickets():
    session_token = session.get('session_token')
    user = db.get_user_by_session(session_token) if session_token else None
    if not user:
        return jsonify({'tickets': []})
    tickets = db.get_user_support_tickets(user_id=user['id'], email=user['email'])
    return jsonify({'tickets': tickets})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"GSSSB CBRT Mock Test Platform running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
