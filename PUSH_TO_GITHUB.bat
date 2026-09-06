@echo off
cd /d "%~dp0"
echo ========================================================
echo   Pushing GSSSB CBRT Exam updates to GitHub ^& Vercel
echo ========================================================
echo.
git add .
git commit -m "Update pricing to 99, 199, 399 and sync QR code"
git push origin main
echo.
echo ========================================================
echo   SUCCESS! Latest code pushed to GitHub / Vercel.
echo   Please wait 1 minute for Vercel to build, then
echo   refresh the exam page on your phone.
echo ========================================================
pause
