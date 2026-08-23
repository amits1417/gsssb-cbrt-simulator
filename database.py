import sqlite3
import os
import json
import uuid
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

def _get_db_path():
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or os.environ.get('LAMBDA_TASK_ROOT'):
        temp_db = '/tmp/database.db'
        orig_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
        if not os.path.exists(temp_db) and os.path.exists(orig_db):
            try:
                import shutil
                shutil.copyfile(orig_db, temp_db)
            except Exception:
                pass
        return temp_db
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

DB_PATH = _get_db_path()



def _load_dotenv(path=None):
    """Minimal .env loader (no external dependency). Loads KEY=VALUE pairs from
    a .env file in the project root into os.environ if not already set."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

_load_dotenv()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            is_paid INTEGER DEFAULT 0,
            paid_at TEXT,
            expires_at TEXT,
            current_session_token TEXT,
            device_info TEXT,
            last_ip TEXT,
            last_active TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Test attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_id TEXT NOT NULL,
            total_questions INTEGER DEFAULT 100,
            correct_count INTEGER DEFAULT 0,
            incorrect_count INTEGER DEFAULT 0,
            unattempted_count INTEGER DEFAULT 0,
            net_score REAL DEFAULT 0.0,
            accuracy REAL DEFAULT 0.0,
            time_taken_seconds INTEGER DEFAULT 0,
            answers_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 3. Payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL DEFAULT 300.0,
            payment_method TEXT DEFAULT 'UPI',
            utr_number TEXT,
            notes TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            approved_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 4. Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # 5. Support Tickets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            category TEXT DEFAULT 'General Support',
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration checks for columns
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN google_id TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN avatar_url TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN trusted_device_id TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN current_device_id TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN otp_code TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN otp_expires_at TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN user_uid TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN device_resets_count INTEGER DEFAULT 0')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE support_tickets ADD COLUMN admin_reply TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE support_tickets ADD COLUMN replied_at TEXT')
    except:
        pass

    # Insert default settings if not exists
    default_settings = [
        ('subscription_price', '300'),
        ('upi_id', 'amit109881.rzp@rxairtel'),
        ('upi_name', 'AMIT (cce)'),
        ('free_papers_count', '2'),
        ('allow_auto_activation', '0'),
        ('announcement', 'Welcome to GSSSB CCE Mock Test Portal! Paper 1 & 2 are free. Unlock all 71 papers.')
    ]
    for key, val in default_settings:
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))
        
    # Create default Admin if not exists
    admin_email = 'admin@gsssb.com'
    cursor.execute('SELECT id FROM users WHERE email = ?', (admin_email,))
    admin = cursor.fetchone()
    if not admin:
        admin_pass = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (name, email, phone, password_hash, is_paid, is_admin)
            VALUES (?, ?, ?, ?, 1, 1)
        ''', ('Super Admin', admin_email, '9999999999', admin_pass))
        
    conn.commit()
    conn.close()

# ----------------- User Auth & Session Functions -----------------

def _generate_user_uid():
    """Generate a unique, non-reusable public user ID (e.g. GSSSB-AB12CD34).
    Uniqueness is enforced against the DB; deleted UIDs are never reassigned
    because we always mint a fresh random code."""
    import string, random
    while True:
        code = 'GSSSB' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        conn = get_db_connection()
        row = conn.execute('SELECT 1 FROM users WHERE user_uid = ?', (code,)).fetchone()
        conn.close()
        if not row:
            return code

def create_user(name, email, phone, password, device_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    phone_clean = phone.strip() if phone else ''
    
    if not phone_clean or len(phone_clean) < 10 or not phone_clean.isdigit():
        conn.close()
        return None, "A valid 10-digit mobile number is compulsory."
        
    cursor.execute('SELECT id FROM users WHERE email = ?', (email_clean,))
    if cursor.fetchone():
        conn.close()
        return None, "Email is already registered. Please log in."
        
    pw_hash = generate_password_hash(password)
    session_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    # First device becomes the trusted device (max 1 device policy)
    trusted_device = device_id or str(uuid.uuid4())
    user_uid = _generate_user_uid()
    
    cursor.execute('''
        INSERT INTO users (name, email, phone, password_hash, current_session_token, current_device_id, trusted_device_id, user_uid, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name.strip(), email_clean, phone_clean, pw_hash, session_token, trusted_device, trusted_device, user_uid, now_str))
    
    user_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = dict(cursor.fetchone())
    conn.close()
    
    return user, session_token

def authenticate_user(email, password, device_id=None, device_info=None, ip_address=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'No account found with this email.'}
        
    user = dict(row)
    if not check_password_hash(user['password_hash'], password):
        conn.close()
        return {'status': 'ERROR', 'message': 'Incorrect password.'}
        
    # Strict 1-Device Lock policy:
    # - If no trusted device is bound yet, this device becomes bound (first login).
    # - If this device matches the bound device, login directly.
    # - If this is a DIFFERENT device, block login immediately to prevent account sharing.
    # Admin accounts are exempt and can log in from any device.
    trusted = user.get('trusted_device_id')
    is_admin = user.get('is_admin')
    if (device_id and trusted and trusted != device_id) and not is_admin:
        conn.close()
        return {
            'status': 'ERROR',
            'message': '🔒 Multi-Device Login Blocked: This account is registered on another device. Login from a second device is strictly prohibited. (આ એકાઉન્ટ બીજા ઉપકરણ પર રજીસ્ટર થયેલ છે. એકાઉન્ટ શેરિંગ અટકાવવા માટે બીજા ડિવાઇસમાંથી લોગિન બંધ કરેલ છે. નવું ડિવાઇસ બદલવા માટે Self-Reset Device નો ઉપયોગ કરો અથવા એડમિનનો સંપર્ક કરો.)'
        }
    
    # Same device (or first ever login) -> issue session immediately.
    new_session_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    device_to_set = device_id or trusted or str(uuid.uuid4())
    
    cursor.execute('''
        UPDATE users
        SET current_session_token = ?, current_device_id = ?, trusted_device_id = ?, device_info = ?, last_ip = ?, last_active = ?
        WHERE id = ?
    ''', (new_session_token, device_to_set, device_to_set, device_info or 'Unknown Device', ip_address or '127.0.0.1', now_str, user['id']))
    
    conn.commit()
    user['current_session_token'] = new_session_token
    user.pop('password_hash', None)
    conn.close()
    
    return {'status': 'OK', 'user': user, 'token': new_session_token}

def authenticate_google_user(email, name, device_id=None, device_info=None, ip_address=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    
    new_session_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    device_to_set = device_id or str(uuid.uuid4())
    
    if row:
        user = dict(row)
        trusted = user.get('trusted_device_id')
        is_admin = user.get('is_admin')
        if (device_id and trusted and trusted != device_id) and not is_admin:
            conn.close()
            return {
                'status': 'ERROR',
                'message': '🔒 Multi-Device Login Blocked: This account is registered on another device.'
            }
        
        cursor.execute('''
            UPDATE users
            SET current_session_token = ?, current_device_id = ?, last_ip = ?, last_active = ?, device_info = ?
            WHERE id = ?
        ''', (new_session_token, device_to_set, ip_address or '127.0.0.1', now_str, device_info or 'Google Auth', user['id']))
        conn.commit()
        user['current_session_token'] = new_session_token
        user.pop('password_hash', None)
        conn.close()
        return {'status': 'OK', 'user': user, 'token': new_session_token}
    else:
        # Create user for first-time Google sign in
        pw_hash = generate_password_hash(str(uuid.uuid4()))
        user_uid = _generate_user_uid()
        cursor.execute('''
            INSERT INTO users (name, email, phone, password_hash, current_session_token, current_device_id, trusted_device_id, user_uid, last_active, device_info, last_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name.strip() or email_clean.split('@')[0], email_clean, '', pw_hash, new_session_token, device_to_set, device_to_set, user_uid, now_str, device_info or 'Google Auth', ip_address or '127.0.0.1'))
        user_id = cursor.lastrowid
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = dict(cursor.fetchone())
        user.pop('password_hash', None)
        conn.close()
        return {'status': 'OK', 'user': user, 'token': new_session_token}

def _generate_otp():
    import random
    return str(random.randint(100000, 999999))

def _store_otp(cursor, conn, user_id, otp):
    expires = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()
    cursor.execute('''
        UPDATE users SET otp_code = ?, otp_expires_at = ? WHERE id = ?
    ''', (otp, expires, user_id))
    conn.commit()

def _send_otp_sms(phone, otp, name=None, email=None):
    """Send OTP to the user via a configured channel.

    Channel is chosen with the SMS_PROVIDER env var:
      - 'dev'    (default) : prints OTP to server console; returns OTP when
                             SMS_DEBUG=1 (for local testing only).
      - 'msg91'  : MSG91 OTP API  (needs MSG91_AUTHKEY, MSG91_TEMPLATE_ID).
      - 'twilio' : Twilio SMS     (needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                                  TWILIO_FROM_NUMBER).
      - 'email'  : FREE SMTP email (needs SMTP_HOST/PORT/USER/PASS/FROM).

    When a real channel is configured the OTP is NEVER returned to the client.
    """
    provider = os.environ.get('SMS_PROVIDER', 'dev').lower()

    if provider == 'email':
        return _send_email_otp(email, otp, name)
    if provider == 'msg91':
        return _send_msg91(phone, otp)
    if provider == 'twilio':
        return _send_twilio(phone, otp)

    # Dev mode
    dest = phone or email or 'unknown'
    print(f"[OTP] Login OTP for {name or ''} ({dest}): {otp}")
    return otp if os.environ.get('SMS_DEBUG', '1') == '1' else None


def _send_email_otp(email, otp, name=None):
    if not email:
        print(f"[OTP] (no email on record) OTP for {name or ''}: {otp}")
        return None
    host = os.environ.get('SMTP_HOST')
    user = os.environ.get('SMTP_USER')
    pwd = os.environ.get('SMTP_PASS')
    if not (host and user and pwd):
        print("[OTP] SMTP not configured; falling back to console log.")
        print(f"[OTP] (email) OTP for {email}: {otp}")
        # In dev we still surface the OTP for easy testing.
        return otp if os.environ.get('SMS_DEBUG', '1') == '1' else None
    import smtplib
    from email.message import EmailMessage
    port = int(os.environ.get('SMTP_PORT', '587'))
    sender = os.environ.get('SMTP_FROM', user)
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Your GSSSB CCE Login OTP'
        msg['From'] = sender
        msg['To'] = email
        msg.set_content(
            f"Hello {name or 'Candidate'},\n\n"
            f"Your one-time password (OTP) to authorize this device is: {otp}\n"
            f"It is valid for 10 minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"- GSSSB CCE Mocktest Team"
        )
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        print(f"[OTP] Email sent to {email}")
        return None
    except Exception as e:
        print(f"[OTP] Email send failed: {e}")
        # In dev mode, still surface the OTP so local testing works even with
        # broken/placeholder SMTP credentials.
        return otp if os.environ.get('SMS_DEBUG', '1') == '1' else None


def _send_msg91(phone, otp):
    import requests
    authkey = os.environ.get('MSG91_AUTHKEY')
    template_id = os.environ.get('MSG91_TEMPLATE_ID')
    if not authkey:
        print("[OTP] MSG91_AUTHKEY not set; falling back to console log.")
        print(f"[OTP] (MSG91) OTP for {phone}: {otp}")
        return None
    # MSG91 expects the mobile number with country code (e.g. 919999999999)
    mobile = phone if phone.startswith('91') else '91' + phone.lstrip('+')
    payload = {
        'authkey': authkey,
        'mobile': mobile,
        'otp': otp,
        'otp_expiry': 10,
    }
    if template_id:
        payload['template_id'] = template_id
    try:
        resp = requests.post('https://api.msg91.com/api/v5/otp', json=payload, timeout=10)
        print(f"[OTP] MSG91 send status: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[OTP] MSG91 send failed: {e}")
    return None


def _send_twilio(phone, otp):
    import requests
    sid = os.environ.get('TWILIO_ACCOUNT_SID')
    token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_FROM_NUMBER')
    if not (sid and token and from_number):
        print("[OTP] Twilio credentials missing; falling back to console log.")
        print(f"[OTP] (Twilio) OTP for {phone}: {otp}")
        return None
    to_number = phone if phone.startswith('+') else '+91' + phone.lstrip('+')
    try:
        resp = requests.post(
            f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
            auth=(sid, token),
            data={'To': to_number, 'From': from_number,
                  'Body': f'Your GSSSB CCE login OTP is {otp}. Valid for 10 minutes.'},
            timeout=10
        )
        print(f"[OTP] Twilio send status: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[OTP] Twilio send failed: {e}")
    return None

def resend_otp(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'No account found with this email.'}
    user = dict(row)
    otp = _generate_otp()
    _store_otp(cursor, conn, user['id'], otp)
    dev_otp = _send_otp_sms(user.get('phone'), otp, user.get('name'), user.get('email'))
    conn.close()
    return {'status': 'OK', 'dev_otp': dev_otp,
            'message': 'A new OTP has been sent to your registered email address.'}

def verify_otp_and_login(email, otp, device_id=None, device_info=None, ip_address=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'No account found with this email.'}
    user = dict(row)
    
    now = datetime.datetime.now().isoformat()
    stored_otp = user.get('otp_code')
    expires = user.get('otp_expires_at')
    if not stored_otp or not expires:
        conn.close()
        return {'status': 'ERROR', 'message': 'No OTP requested. Please login again.'}
    if datetime.datetime.now() > datetime.datetime.fromisoformat(expires):
        conn.close()
        return {'status': 'ERROR', 'message': 'OTP has expired. Please request a new one.'}
    if str(otp).strip() != str(stored_otp):
        conn.close()
        return {'status': 'ERROR', 'message': 'Invalid OTP. Please try again.'}
    
    # OTP correct -> authorize THIS device as the (single) trusted device.
    # This displaces any previously trusted device (max 1 device policy).
    new_session_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    device_to_set = device_id or str(uuid.uuid4())
    cursor.execute('''
        UPDATE users
        SET current_session_token = ?, current_device_id = ?, trusted_device_id = ?, device_info = ?, last_ip = ?, last_active = ?, otp_code = NULL, otp_expires_at = NULL
        WHERE id = ?
    ''', (new_session_token, device_to_set, device_to_set, device_info or 'Unknown Device', ip_address or '127.0.0.1', now_str, user['id']))
    conn.commit()
    user['current_session_token'] = new_session_token
    user.pop('password_hash', None)
    conn.close()
    return {'status': 'OK', 'user': user, 'token': new_session_token}

def request_forgot_password_otp(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'No account found with this email address (આ ઈમેલ સાથે કોઈ ખાતું મળ્યું નથી).'}
    
    user = dict(row)
    otp = _generate_otp()
    _store_otp(cursor, conn, user['id'], otp)
    
    dev_otp = _send_email_otp(user['email'], otp, user.get('name'))
    conn.close()
    return {'status': 'OK', 'message': f'6-Digit Password Reset OTP has been sent to {user["email"]}.', 'dev_otp': dev_otp}

def reset_password_with_otp(email, otp, new_password, device_id=None, device_info=None, ip_address=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    otp_clean = str(otp).strip()
    
    if not new_password or len(new_password) < 6:
        conn.close()
        return {'status': 'ERROR', 'message': 'New password must be at least 6 characters long.'}
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'Account not found.'}
        
    user = dict(row)
    stored_otp = user.get('otp_code')
    expires_at = user.get('otp_expires_at')
    
    if not stored_otp or str(stored_otp).strip() != otp_clean:
        conn.close()
        return {'status': 'ERROR', 'message': 'Invalid OTP code. Please check your email and try again.'}
        
    if expires_at:
        try:
            if datetime.datetime.now() > datetime.datetime.fromisoformat(expires_at):
                conn.close()
                return {'status': 'ERROR', 'message': 'OTP has expired. Please request a new one.'}
        except:
            pass
        
    new_pw_hash = generate_password_hash(new_password)
    new_session = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    device_to_set = device_id or user.get('trusted_device_id') or str(uuid.uuid4())
    
    cursor.execute('''
        UPDATE users
        SET password_hash = ?, otp_code = NULL, otp_expires_at = NULL,
            current_session_token = ?, current_device_id = ?, last_active = ?, last_ip = ?, device_info = ?
        WHERE id = ?
    ''', (new_pw_hash, new_session, device_to_set, now_str, ip_address or '127.0.0.1', device_info or 'Web Browser', user['id']))
    conn.commit()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user['id'],))
    updated_user = dict(cursor.fetchone())
    updated_user.pop('password_hash', None)
    conn.close()
    return {'status': 'OK', 'user': updated_user, 'token': new_session}


def google_auth_user(email, name, google_id=None, avatar_url=None, phone=None, device_info=None, ip_address=None, device_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    name_clean = name.strip() if name else email_clean.split('@')[0]
    
    new_session_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    
    if row:
        user = dict(row)
        user_id = user['id']
        trusted = user.get('trusted_device_id')
        is_admin = user.get('is_admin')
        if (device_id and trusted and trusted != device_id) and not is_admin:
            conn.close()
            return {
                'status': 'ERROR',
                'message': '🔒 Multi-Device Login Blocked: This account is registered on another device. (આ એકાઉન્ટ બીજા ઉપકરણ પર રજીસ્ટર થયેલ છે. એકાઉન્ટ શેરિંગ અટકાવવા માટે બીજા ડિવાઇસમાંથી લોગિન બંધ કરેલ છે.)'
            }
        cursor.execute('''
            UPDATE users
            SET current_session_token = ?, current_device_id = ?, trusted_device_id = COALESCE(trusted_device_id, ?), device_info = ?, last_ip = ?, last_active = ?,
                google_id = COALESCE(google_id, ?), avatar_url = COALESCE(avatar_url, ?),
                phone = CASE WHEN phone IS NULL OR phone = '' THEN ? ELSE phone END
            WHERE id = ?
        ''', (new_session_token, device_id or 'google_device', device_id or 'google_device', device_info or 'Google Sign-In Device', ip_address or '127.0.0.1', now_str, 
              google_id, avatar_url, phone or '', user_id))
        conn.commit()
        is_new = False
    else:
        # Create new user via Google
        pw_hash = generate_password_hash(str(uuid.uuid4())) # random secure hash
        dev_id = device_id or 'google_device'
        cursor.execute('''
            INSERT INTO users (name, email, phone, password_hash, google_id, avatar_url, current_session_token, current_device_id, trusted_device_id, device_info, last_ip, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name_clean, email_clean, phone or '', pw_hash, google_id, avatar_url, new_session_token, dev_id, dev_id, device_info or 'Google Sign-In Device', ip_address or '127.0.0.1', now_str))
        user_id = cursor.lastrowid
        conn.commit()
        is_new = True
        
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = dict(cursor.fetchone())
    user.pop('password_hash', None)
    conn.close()
    
    return user, new_session_token, is_new

def update_user_phone(user_id, phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    phone_clean = phone.strip()
    if not phone_clean or len(phone_clean) < 10 or not phone_clean.isdigit():
        conn.close()
        return False, "A valid 10-digit mobile number is compulsory."
    cursor.execute('UPDATE users SET phone = ? WHERE id = ?', (phone_clean, user_id))
    conn.commit()
    conn.close()
    return True, "Phone number updated successfully."

def check_and_expire_subscriptions():
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().isoformat()
    cursor.execute('''
        UPDATE users
        SET is_paid = 0
        WHERE is_paid = 1 AND expires_at IS NOT NULL AND expires_at < ?
    ''', (now_str,))
    expired_count = cursor.rowcount
    conn.commit()
    conn.close()
    return expired_count

def get_user_by_session(session_token, device_id=None):
    if not session_token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE current_session_token = ?', (session_token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    # Device binding: if a device_id is supplied and differs from the session's
    # registered device, treat the session as revoked (guards against token reuse
    # on a non-trusted device).
    if device_id and row['current_device_id'] and row['current_device_id'] != device_id:
        conn.close()
        return None
        
    user = dict(row)
    user.pop('password_hash', None)
    
    # Check if subscription has expired
    if user.get('is_paid') and user.get('expires_at') and not user.get('is_admin'):
        try:
            expires_dt = datetime.datetime.fromisoformat(user['expires_at'])
            now = datetime.datetime.now()
            if now > expires_dt:
                # Expired! Automatically end subscription
                cursor.execute('UPDATE users SET is_paid = 0 WHERE id = ?', (user['id'],))
                conn.commit()
                user['is_paid'] = 0
                user['subscription_expired'] = True
            else:
                remaining_delta = expires_dt - now
                user['days_remaining'] = max(1, remaining_delta.days)
                user['expires_date_formatted'] = expires_dt.strftime('%d %b %Y')
        except Exception:
            pass
            
    conn.close()
    return user

def get_user_exam_attempts_map(user_id):
    if not user_id:
        return {}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            exam_id, 
            MAX(net_score) as best_score, 
            MAX(accuracy) as best_accuracy, 
            COUNT(id) as attempts_count, 
            MAX(created_at) as last_attempted
        FROM test_attempts 
        WHERE user_id = ? 
        GROUP BY exam_id
    ''', (user_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {r['exam_id']: r for r in rows}

def logout_user(session_token):
    if not session_token:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET current_session_token = NULL WHERE current_session_token = ?', (session_token,))
    conn.commit()
    conn.close()

def delete_user(user_id, admin_id=None):
    """Permanently delete a user and all their linked data (payments + test
    attempts). The user's public UID is never reassigned to another user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if admin_id and int(user_id) == int(admin_id):
        conn.close()
        return False, "You cannot delete your own admin account."
    cursor.execute('SELECT id, is_admin FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    cursor.execute('DELETE FROM test_attempts WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM payments WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True, "User and all linked data deleted successfully."

def reset_user_device(user_id):
    """Reset a user's bound trusted device so they can log in from a new device."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET trusted_device_id = NULL, current_device_id = NULL, current_session_token = NULL, device_resets_count = 0
        WHERE id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()
    return True, "Device reset successfully. Candidate can now bind a new device on next login."

def request_device_reset_otp(email, password):
    """Generate and send OTP for candidate self-service device reset (max 2 resets allowed)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'No account found with this email.'}
    
    user = dict(row)
    if not check_password_hash(user['password_hash'], password):
        conn.close()
        return {'status': 'ERROR', 'message': 'Incorrect password.'}
    
    resets_count = user.get('device_resets_count') or 0
    if resets_count >= 2 and not user.get('is_admin'):
        conn.close()
        return {
            'status': 'ERROR',
            'message': '🔒 Maximum Device Resets Reached (2/2): You have used all 2 self-service device resets. (તમે 2 વખત ડિવાઇસ રીસેટ કરવાની સીમા પૂર્ણ કરી લીધી છે. આગળ ડિવાઇસ બદલવા માટે એડમિનનો સંપર્ક કરો.)'
        }
    
    otp = _generate_otp()
    _store_otp(cursor, conn, user['id'], otp)
    dev_otp = _send_otp_sms(user.get('phone'), otp, user.get('name'), user.get('email'))
    conn.close()
    
    return {
        'status': 'OK',
        'email': email_clean,
        'resets_used': resets_count,
        'remaining_resets': 2 - resets_count,
        'message': f'Verification OTP sent to {email_clean}. (રજીસ્ટર્ડ ઈમેઈલ પર OTP મોકલવામાં આવ્યો છે.)',
        'dev_otp': dev_otp
    }

def confirm_device_reset(email, otp, new_device_id=None, device_info=None, ip_address=None):
    """Verify OTP and complete candidate self-service device reset."""
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email_clean,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'status': 'ERROR', 'message': 'No account found with this email.'}
    user = dict(row)
    
    stored_otp = user.get('otp_code')
    expires = user.get('otp_expires_at')
    if not stored_otp or not expires:
        conn.close()
        return {'status': 'ERROR', 'message': 'No OTP requested. Please try again.'}
    if datetime.datetime.now() > datetime.datetime.fromisoformat(expires):
        conn.close()
        return {'status': 'ERROR', 'message': 'OTP has expired. Please request a new one.'}
    if str(otp).strip() != str(stored_otp):
        conn.close()
        return {'status': 'ERROR', 'message': 'Invalid OTP. Please try again. (ખોટો OTP છે.)'}
    
    resets_count = (user.get('device_resets_count') or 0) + 1
    new_session_token = str(uuid.uuid4())
    now_str = datetime.datetime.now().isoformat()
    device_to_set = new_device_id or str(uuid.uuid4())
    
    cursor.execute('''
        UPDATE users
        SET trusted_device_id = ?, current_device_id = ?, current_session_token = ?, device_info = ?, last_ip = ?, last_active = ?,
            device_resets_count = ?, otp_code = NULL, otp_expires_at = NULL
        WHERE id = ?
    ''', (device_to_set, device_to_set, new_session_token, device_info or 'New Registered Device', ip_address or '127.0.0.1', now_str, resets_count, user['id']))
    
    conn.commit()
    user['current_session_token'] = new_session_token
    user['trusted_device_id'] = device_to_set
    user['device_resets_count'] = resets_count
    user.pop('password_hash', None)
    conn.close()
    
    return {
        'status': 'OK',
        'message': f'Device reset successfully! This device is now bound. (ડિવાઇસ સફળતાપૂર્વક રીસેટ થઈ ગયું છે! {resets_count}/2 સીમા વપરાયેલ)',
        'user': user,
        'token': new_session_token
    }

def get_user_full_details(user_id):
    """Return full user record + all linked payments + test attempts + stats.
    Everything is linked via user_id (the key used by payments & attempts)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    user = dict(row)
    user.pop('password_hash', None)
    cursor.execute('SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC', (user_id,))
    payments = [dict(r) for r in cursor.fetchall()]
    cursor.execute('SELECT * FROM test_attempts WHERE user_id = ? ORDER BY id DESC', (user_id,))
    attempts = [dict(r) for r in cursor.fetchall()]
    stats = get_user_stats(user_id)
    conn.close()
    return {'user': user, 'payments': payments, 'attempts': attempts, 'stats': stats}

def get_user_by_uid(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_uid = ?', (uid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        u = dict(row)
        u.pop('password_hash', None)
        return u
    return None

# ----------------- Exam Attempt & Analytics Functions -----------------

def save_test_attempt(user_id, exam_id, total_q, correct, incorrect, unattempted, net_score, time_taken, answers_dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    accuracy = 0.0
    attempted_count = correct + incorrect
    if attempted_count > 0:
        accuracy = round((correct / attempted_count) * 100, 1)
        
    answers_json = json.dumps(answers_dict)
    
    cursor.execute('''
        INSERT INTO test_attempts (user_id, exam_id, total_questions, correct_count, incorrect_count, 
                                   unattempted_count, net_score, accuracy, time_taken_seconds, answers_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, exam_id, total_q, correct, incorrect, unattempted, net_score, accuracy, time_taken, answers_json))
    
    attempt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return attempt_id

def get_user_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Aggregated stats
    cursor.execute('''
        SELECT 
            COUNT(id) as total_tests,
            COALESCE(AVG(net_score), 0.0) as avg_score,
            COALESCE(MAX(net_score), 0.0) as best_score,
            COALESCE(SUM(correct_count), 0) as total_correct,
            COALESCE(SUM(incorrect_count), 0) as total_incorrect,
            COALESCE(SUM(unattempted_count), 0) as total_unattempted,
            COALESCE(AVG(time_taken_seconds), 0) as avg_time
        FROM test_attempts
        WHERE user_id = ?
    ''', (user_id,))
    agg = dict(cursor.fetchone())
    
    # Calculate overall accuracy
    tot_attempted = agg['total_correct'] + agg['total_incorrect']
    if tot_attempted > 0:
        agg['overall_accuracy'] = round((agg['total_correct'] / tot_attempted) * 100, 1)
    else:
        agg['overall_accuracy'] = 0.0
        
    agg['avg_score'] = round(agg['avg_score'], 2)
    agg['best_score'] = round(agg['best_score'], 2)
    
    # Recent test history for graphs (last 15 tests)
    cursor.execute('''
        SELECT id, exam_id, net_score, correct_count, incorrect_count, unattempted_count, accuracy, time_taken_seconds, created_at
        FROM test_attempts
        WHERE user_id = ?
        ORDER BY created_at ASC
    ''', (user_id,))
    history_rows = cursor.fetchall()
    history = [dict(r) for r in history_rows]
    
    # User's Rank in Leaderboard
    cursor.execute('''
        SELECT user_id, AVG(net_score) as user_avg
        FROM test_attempts
        GROUP BY user_id
        ORDER BY user_avg DESC
    ''')
    rankings = cursor.fetchall()
    user_rank = 0
    total_ranked_users = len(rankings)
    for idx, r in enumerate(rankings):
        if r['user_id'] == user_id:
            user_rank = idx + 1
            break
            
    percentile = 0.0
    if total_ranked_users > 0 and user_rank > 0:
        percentile = round(((total_ranked_users - user_rank + 1) / total_ranked_users) * 100, 1)
        
    agg['user_rank'] = user_rank if user_rank > 0 else "-"
    agg['total_candidates'] = total_ranked_users
    agg['percentile'] = percentile
    agg['history'] = history
    
    conn.close()
    return agg

def get_attempt_details(attempt_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute('SELECT * FROM test_attempts WHERE id = ? AND user_id = ?', (attempt_id, user_id))
    else:
        cursor.execute('SELECT * FROM test_attempts WHERE id = ?', (attempt_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        res = dict(row)
        res['answers'] = json.loads(res['answers_json']) if res['answers_json'] else {}
        return res
    return None

def get_leaderboard(limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            u.id as user_id,
            u.name as candidate_name,
            COUNT(t.id) as tests_completed,
            ROUND(AVG(t.net_score), 2) as average_score,
            ROUND(MAX(t.net_score), 2) as highest_score,
            ROUND(AVG(t.accuracy), 1) as avg_accuracy
        FROM users u
        JOIN test_attempts t ON u.id = t.user_id
        GROUP BY u.id
        HAVING tests_completed > 0
        ORDER BY average_score DESC, highest_score DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    leaderboard = []
    total_count = len(rows)
    for idx, r in enumerate(rows):
        item = dict(r)
        item['rank'] = idx + 1
        item['percentile'] = round(((total_count - idx) / total_count) * 100, 1) if total_count > 0 else 100.0
        leaderboard.append(item)
        
    conn.close()
    return leaderboard

# ----------------- Payment & Admin Functions -----------------

def create_payment_request(user_id, utr_number, amount=300.0, payment_method='UPI', notes=''):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (user_id, amount, payment_method, utr_number, notes, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    ''', (user_id, amount, payment_method, utr_number.strip(), notes))
    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def approve_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    now_str = now.isoformat()
    
    cursor.execute('SELECT user_id, amount FROM payments WHERE id = ?', (payment_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
        
    user_id = row['user_id']
    amount = float(row['amount'])
    
    # Calculate days based on plan amount
    days = 30
    if amount >= 799:
        days = 180
    elif amount >= 499:
        days = 90
    else:
        days = 30
        
    expires_dt = now + datetime.timedelta(days=days)
    expires_str = expires_dt.isoformat()
    
    cursor.execute('''
        UPDATE payments
        SET status = 'approved', approved_at = ?
        WHERE id = ?
    ''', (now_str, payment_id))
    
    cursor.execute('''
        UPDATE users
        SET is_paid = 1, paid_at = ?, expires_at = ?
        WHERE id = ?
    ''', (now_str, expires_str, user_id))
    
    conn.commit()
    conn.close()
    return True

def toggle_user_subscription(user_id, is_paid, days=30, plan_name='Manual Admin Plan', amount=300):
    conn = get_db_connection()
    cursor = conn.cursor()
    if is_paid:
        now = datetime.datetime.now()
        now_str = now.isoformat()
        try:
            days_int = int(days)
        except:
            days_int = 30
            
        if days_int <= 0 or days_int >= 3650: # Lifetime
            expires_str = (now + datetime.timedelta(days=3650)).isoformat()
            duration_label = "Lifetime"
        else:
            expires_str = (now + datetime.timedelta(days=days_int)).isoformat()
            duration_label = f"{days_int} Days"
            
        cursor.execute('''
            UPDATE users
            SET is_paid = 1, paid_at = ?, expires_at = ?
            WHERE id = ?
        ''', (now_str, expires_str, user_id))
        
        # Log entry in payments table for audit & analytics
        try:
            cursor.execute('''
                INSERT INTO payments (user_id, amount, payment_method, utr_number, status, notes, created_at)
                VALUES (?, ?, 'ADMIN_MANUAL', ?, 'approved', ?, ?)
            ''', (user_id, float(amount or 0), f"MANUAL-{str(uuid.uuid4())[:8].upper()}", f"Admin Activated: {plan_name} ({duration_label})", now_str))
        except:
            pass
    else:
        cursor.execute('''
            UPDATE users
            SET is_paid = 0, expires_at = NULL
            WHERE id = ?
        ''', (user_id,))
    conn.commit()
    conn.close()
    return True

def get_all_users_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    cursor.execute('''
        SELECT 
            u.id, u.name, u.email, u.phone, u.is_paid, u.paid_at, u.expires_at, u.is_admin, u.created_at, u.last_active,
            COUNT(t.id) as tests_count,
            COALESCE(AVG(t.net_score), 0) as avg_score
        FROM users u
        LEFT JOIN test_attempts t ON u.id = t.user_id
        GROUP BY u.id
        ORDER BY u.id DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        r['avg_score'] = round(r['avg_score'], 2)
        if r.get('is_admin'):
            r['countdown_text'] = "Lifetime (Admin)"
            r['expires_formatted'] = "Never Expires"
            r['is_valid'] = True
        elif r.get('is_paid') and r.get('expires_at'):
            try:
                exp_dt = datetime.datetime.fromisoformat(r['expires_at'])
                r['expires_formatted'] = exp_dt.strftime('%d %b %Y, %I:%M %p')
                delta = exp_dt - now
                if delta.total_seconds() > 0:
                    days = delta.days
                    hours = int(delta.seconds // 3600)
                    if days > 0:
                        r['countdown_text'] = f"{days}d {hours}h left"
                    else:
                        r['countdown_text'] = f"{hours}h left"
                    r['is_valid'] = True
                else:
                    r['countdown_text'] = "Expired"
                    r['is_valid'] = False
            except Exception:
                r['countdown_text'] = "-"
                r['expires_formatted'] = "-"
        elif r.get('expires_at') and not r.get('is_paid'):
            try:
                exp_dt = datetime.datetime.fromisoformat(r['expires_at'])
                r['expires_formatted'] = exp_dt.strftime('%d %b %Y')
                r['countdown_text'] = "Expired"
                r['is_valid'] = False
            except Exception:
                r['countdown_text'] = "Expired"
                r['expires_formatted'] = "-"
        else:
            r['countdown_text'] = "Free Trial"
            r['expires_formatted'] = "No Active Plan"
            r['is_valid'] = False
    conn.close()
    return rows

def get_all_payments_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, u.user_uid, u.name as user_name, u.email as user_email, u.phone as user_phone
        FROM payments p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.id DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_admin_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(id) FROM users WHERE is_admin = 0')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(id) FROM users WHERE is_paid = 1 AND is_admin = 0')
    paid_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(id) FROM test_attempts')
    total_tests = cursor.fetchone()[0]
    
    cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = "approved"')
    total_revenue = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(id) FROM payments WHERE status = "pending"')
    pending_payments = cursor.fetchone()[0]
    
    conn.close()
    return {
        'total_users': total_users,
        'paid_users': paid_users,
        'free_users': total_users - paid_users,
        'total_tests': total_tests,
        'total_revenue': total_revenue,
        'pending_payments': pending_payments
    }

def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    return settings

def update_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

# --- Support Tickets Functions ---
def create_support_ticket(name, email, phone=None, category='General Support', message='', user_id=None):
    """Create a new candidate support ticket."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO support_tickets (user_id, name, email, phone, category, message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, name.strip(), email.strip().lower(), phone or '', category, message.strip()))
    conn.commit()
    ticket_id = cursor.lastrowid
    conn.close()
    return True, f"Support request submitted successfully! (Ticket #{ticket_id})"

def get_all_support_tickets_admin():
    """Retrieve all candidate support tickets for Super Admin."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, u.user_uid, u.is_paid, u.trusted_device_id
        FROM support_tickets t
        LEFT JOIN users u ON t.user_id = u.id OR LOWER(t.email) = LOWER(u.email)
        ORDER BY t.id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_support_ticket_status(ticket_id, status):
    """Update ticket status ('pending' or 'resolved')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE support_tickets SET status = ? WHERE id = ?', (status, ticket_id))
    conn.commit()
    conn.close()
    return True, "Ticket status updated."

def delete_support_ticket(ticket_id):
    """Delete a support ticket by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM support_tickets WHERE id = ?', (ticket_id,))
    conn.commit()
    conn.close()
    return True, "Support ticket deleted."


def _send_custom_email(email, subject, content, name=None):
    if not email:
        return False
    host = os.environ.get('SMTP_HOST')
    user = os.environ.get('SMTP_USER')
    pwd = os.environ.get('SMTP_PASS')
    if not (host and user and pwd):
        print(f"[EMAIL] SMTP not configured. Custom email to {email}: {subject}")
        return False
    import smtplib
    from email.message import EmailMessage
    port = int(os.environ.get('SMTP_PORT', '587'))
    sender = os.environ.get('SMTP_FROM', user)
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = email
        msg.set_content(content)
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        print(f"[EMAIL] Custom email sent to {email}")
        return True
    except Exception as e:
        print(f"[EMAIL] Custom email send failed: {e}")
        return False

def reply_to_support_ticket(ticket_id, reply_message):
    """Save Admin reply to support ticket and email candidate."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM support_tickets WHERE id = ?', (ticket_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Support ticket not found."
    
    ticket = dict(row)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        UPDATE support_tickets
        SET admin_reply = ?, replied_at = ?, status = 'resolved'
        WHERE id = ?
    ''', (reply_message.strip(), now_str, ticket_id))
    conn.commit()
    conn.close()

    # Send Email Notification to Candidate
    try:
        email_body = f"""Hello {ticket['name']},

Super Admin has responded to your support request (Ticket #{ticket_id}):

--------------------------------------------------
YOUR QUERY:
{ticket['message']}

SUPER ADMIN RESPONSE:
{reply_message.strip()}
--------------------------------------------------

Thank you for using GSSSB CCE Mock Test Portal.
Portal: http://localhost:5000
"""
        _send_custom_email(ticket['email'], f"Response to Support Ticket #{ticket_id} - GSSSB CCE Portal", email_body, ticket['name'])
    except Exception as e:
        pass

    return True, "Reply sent successfully to candidate via Email & In-App Portal!"

def get_user_support_tickets(user_id=None, email=None):
    """Retrieve support tickets submitted by a candidate."""
    conn = get_db_connection()
    cursor = conn.cursor()
    email_clean = email.strip().lower() if email else ''
    cursor.execute('''
        SELECT * FROM support_tickets
        WHERE (user_id IS NOT NULL AND user_id = ?)
           OR (email IS NOT NULL AND LOWER(email) = ?)
        ORDER BY id DESC
    ''', (user_id or -1, email_clean))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Auto-initialize database on import
init_db()
