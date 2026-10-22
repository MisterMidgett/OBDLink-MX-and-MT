@echo off
echo START HERE - Smooth 60fps Final - No duplicates
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (echo Install Git & pause & exit /b 1)
git init
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/MisterMidgett/OBDLink-MX-and-MT.git
git add .
git commit -m "Smooth 60fps - Final cleaned"
echo Make sure repo exists at https://github.com/MisterMidgett/OBDLink-MX-and-MT - if 404 create at https://github.com/new
pause
git push -u origin main
if %ERRORLEVEL% NEQ 0 (git push -f origin main)
echo Done!
pause
