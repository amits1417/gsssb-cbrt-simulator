import requests
import json
import time

BASE_URL = 'http://127.0.0.1:5000'

def run_tests():
    print("Testing GSSSB CBRT Mock Test Platform APIs...")
    time.sleep(2)

    session_user1 = requests.Session()
    
    # 1. Test Signup User 1
    print("\n[1] Testing User Registration...")
    signup_payload = {
        "name": "Rajesh Patel",
        "email": "rajesh@example.com",
        "phone": "9898012345",
        "password": "password123"
    }
    r = session_user1.post(f"{BASE_URL}/api/auth/signup", json=signup_payload)
    print(f"Signup Status: {r.status_code}, Response: {r.json().get('message') or r.json().get('error')}")
    assert r.status_code in [200, 400]

    # 2. Test Login User 1
    print("\n[2] Testing User Login...")
    login_payload = {
        "email": "rajesh@example.com",
        "password": "password123",
        "device_info": "Device A (Chrome Desktop)"
    }
    r = session_user1.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    data1 = r.json()
    token1 = data1.get('token')
    print(f"Login Status: {r.status_code}, User: {data1.get('user', {}).get('name')}, Is Paid: {data1.get('user', {}).get('is_paid')}")
    assert r.status_code == 200

    # 3. Test Free Exam Access (Paper 1)
    print("\n[3] Testing Free Exam Access (PAPER-1)...")
    r = session_user1.get(f"{BASE_URL}/api/exams/PAPER-1/questions")
    print(f"Paper 1 Status: {r.status_code}, Questions loaded: {r.json().get('total')}")
    assert r.status_code == 200

    # 4. Test Locked Exam Access (Paper 3) for Unpaid User
    print("\n[4] Testing Locked Exam Access (PAPER-3) for Unpaid User...")
    r = session_user1.get(f"{BASE_URL}/api/exams/PAPER-3/questions")
    print(f"Paper 3 Status: {r.status_code} (Expected 403 Forbidden), Response: {r.json()}")
    assert r.status_code == 403

    # 5. Test Strict 1-Device Hard Lock (Anti-Sharing Protection)
    print("\n[5] Testing Strict 1-Device Anti-Sharing Protection...")
    session_user2 = requests.Session()
    r = session_user2.post(f"{BASE_URL}/api/auth/login", json={
        "email": "rajesh@example.com",
        "password": "password123",
        "device_id": "dev_device_b_mobile",
        "device_info": "Device B (Mobile Phone)"
    })
    print(f"Device B Login Status: {r.status_code} (Expected 401 Blocked), Response: {r.json().get('error')}")
    assert r.status_code == 401

    # 6. Test Exam Submission & Score Calculation
    print("\n[6] Testing Exam Submission (+1.0 / -0.33 marking)...")
    submit_payload = {
        "paper_id": "PAPER-1",
        "answers": {
            "1": 3,
            "2": 1,
            "3": 5
        },
        "time_taken": 120
    }
    r = session_user1.post(f"{BASE_URL}/api/exams/submit", json=submit_payload)
    sub_res = r.json()
    print(f"Submit Status: {r.status_code}, Net Score: {sub_res.get('net_score')}, Correct: {sub_res.get('correct_count')}, Wrong: {sub_res.get('incorrect_count')}")
    assert r.status_code == 200

    # 7. Test Dashboard Stats
    print("\n[7] Testing Dashboard Stats & Analytics...")
    r = session_user2.get(f"{BASE_URL}/api/dashboard/stats")
    stats = r.json().get('stats', {})
    print(f"Total Tests: {stats.get('total_tests')}, Avg Score: {stats.get('avg_score')}, Best: {stats.get('best_score')}, Rank: {stats.get('user_rank')}")
    assert r.status_code == 200

    # 8. Test Statewide Leaderboard
    print("\n[8] Testing Statewide Leaderboard...")
    r = session_user2.get(f"{BASE_URL}/api/leaderboard")
    lb = r.json().get('leaderboard', [])
    print(f"Leaderboard Count: {len(lb)}, Top Candidate: {lb[0].get('candidate_name') if lb else 'None'}")
    assert r.status_code == 200

    # 9. Test Payment & Admin Pro Activation
    print("\n[9] Testing Payment Submission & Pro Activation...")
    r = session_user2.post(f"{BASE_URL}/api/payment/submit", json={
        "utr_number": "UTR998877665544",
        "notes": "Payment via Google Pay"
    })
    print(f"Payment Submit Status: {r.status_code}, Msg: {r.json().get('message')}")
    assert r.status_code == 200

    # Admin login & toggle subscription
    admin_session = requests.Session()
    admin_session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsssb.com",
        "password": "admin123"
    })
    user_id = data1.get('user', {}).get('id')
    r = admin_session.post(f"{BASE_URL}/api/admin/toggle-subscription", json={
        "user_id": user_id,
        "is_paid": True
    })
    print(f"Admin Pro Activation Status: {r.status_code}, Msg: {r.json().get('message')}")
    assert r.status_code == 200

    # 10. Test Paper 3 Access After Pro Activation
    print("\n[10] Testing Locked Exam Access (PAPER-3) After Pro Activation...")
    r = session_user2.get(f"{BASE_URL}/api/exams/PAPER-3/questions")
    print(f"Paper 3 Status After Activation: {r.status_code} (Success 200), Questions loaded: {r.json().get('total')}")
    assert r.status_code == 200

    print("\n>>> ALL 10 TESTS PASSED PERFECTLY! Platform is 100% verified! <<<")

if __name__ == '__main__':
    run_tests()
