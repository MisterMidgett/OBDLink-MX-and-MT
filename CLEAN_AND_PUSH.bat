@echo off
echo Cleaning and pushing - Smooth 60fps Final
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (echo Install Git first & pause & exit /b 1)
if not exist ".git" (git init & git branch -M main)
git remote remove origin 2>nul
git remote add origin https://github.com/MisterMidgett/OBDLink-MX-and-MT.git
git add .
git commit -m "Smooth 60fps - Final cleaned - No duplicates" 2>nul
git branch -M main
git push -u origin main
if %ERRORLEVEL% NEQ 0 (git push -f origin main)
echo Done! Check https://github.com/MisterMidgett/OBDLink-MX-and-MT/actions
pause
