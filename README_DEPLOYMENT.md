# GSSSB CBRT Mock Test SaaS Platform - Deployment & Setup Guide

---

## 🚀 1. Local Testing (Apne Computer Par Kaise Chalayein)

1. Open Terminal / PowerShell in this folder:
   ```powershell
   cd "C:\Users\admin\.gemini\antigravity\scratch\GSSSB_CBRT_Simulator"
   ```

2. Run the application:
   ```powershell
   python app.py
   ```

3. Open your browser and go to:
   👉 **`http://localhost:5000`**

### 🔑 Default Admin Account:
- **Email:** `admin@gsssb.com`
- **Password:** `admin123`
- **Admin URL:** `http://localhost:5000/admin`

---

## 🌐 2. Website Ko Free Me Live Kaise Karein (Free Cloud Hosting)

Aap is website ko **Render.com** ya **Railway.app** par 100% Free me live kar sakte hain:

### Option A: Render.com (Recommended - Free & Fast)
1. **GitHub Par Upload Karein:**
   - [GitHub.com](https://github.com) par ek new private ya public repository banayein.
   - Apne is folder ka code GitHub par push karein:
     ```bash
     git init
     git add .
     git commit -m "Initial GSSSB Platform"
     git branch -M main
     git remote add origin https://github.com/YOUR_USERNAME/gsssb-cbrt-platform.git
     git push -u origin main
     ```

2. **Render.com Par Deploy Karein:**
   - [Render.com](https://render.com) par free account banayein.
   - **New +** -> **Web Service** select karein.
   - Apni GitHub repository connect karein.
   - Settings me:
     - **Name:** `gsssb-cbrt-simulator`
     - **Runtime:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `gunicorn app:app`
   - Click **Deploy Web Service**!
   - 2 minutes me aapko aapki live link mil jayegi: `https://gsssb-cbrt-simulator.onrender.com`

---

## 💰 3. Subscription & Payment System Setup (₹300)

1. Admin portal par login karein: `http://your-site/admin`
2. **Platform Configurations** me apna:
   - **UPI ID:** (e.g. `yourname@okaxis` ya `yourname@paytm`)
   - **Payee Name:** (e.g. `GSSSB Exam Portal`)
   - **Price:** `300`
3. Jab student payment karega:
   - Dynamic UPI QR Code generate hoga.
   - Student QR scan karke ₹300 pay karega aur **UTR / Transaction ID** submit karega.
   - Admin Panel me **Approve** button dabaate hi candidate ka account instantly Pro me unlock ho jayega!

---

## 🔒 4. Single Device & Anti-Sharing Security Feature
- Har student ka ek time par sirf **ek hi device** par login allowed hai.
- Agar student apna password kisi dost ko share karega aur wo login karega, to pehle wale ka active test aur session **turant automatically terminate aur logout** ho jayega.

---

## 📊 5. Features Included
- ✅ 71 Full GSSSB Mock Papers (7,100 Gujarati & English Scanned MCQs)
- ✅ 2 Free Mock Tests (Paper 1 & 2) + 69 Pro Mock Tests (Paper 3-71 locked)
- ✅ Official TCS Exam Simulator Interface + Palette + 60-minute Timer
- ✅ Negative Marking (+1.0 for Correct, -0.33 for Incorrect, 0 for Unattempted)
- ✅ Student Dashboard with 3 Visual Chart.js Analytics Graphs
- ✅ Question-by-Question Solution Review Panel
- ✅ Real-time Gujarat Statewide Leaderboard with Rank & Percentile
- ✅ Super Admin Management Portal (User management & 1-click unlock)
