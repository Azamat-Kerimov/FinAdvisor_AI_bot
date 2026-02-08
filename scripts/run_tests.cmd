@echo off
REM Запуск автотестов API из корня проекта.
REM Требования: API запущен на http://localhost:8000 с APP_ENV=test, в БД есть user id=1.
REM Зависимости: pip install -r _unpublished/requirements-test.txt (один раз).

cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv не найден. Создайте: python -m venv venv
    exit /b 1
)

echo Запуск pytest _unpublished/tests/ ...
venv\Scripts\python -m pytest _unpublished/tests/ -v
exit /b %ERRORLEVEL%
