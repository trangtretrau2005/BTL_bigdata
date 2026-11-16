@echo off
title AI Doc RAG - Streamlit App
echo Dang khoi dong AI Doc RAG...
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start_project.ps1"
if errorlevel 1 exit /b 1
pause
