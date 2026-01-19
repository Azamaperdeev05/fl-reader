@echo off
chcp 65001 >nul
echo ============================================
echo    Lumina Reader - Іске қосу скрипті
echo ============================================
echo.

REM Tor табу және іске қосу
echo [1/3] Tor іске қосылуда...
start "" "C:\Users\%USERNAME%\Desktop\Tor Browser\Browser\TorBrowser\Tor\tor.exe"
echo      ✓ Tor іске қосылды (жаңа терминалда)
echo.

REM 5 секунд күту (Tor қосылуына)
echo [2/3] Tor қосылуын күтуде (10 секунд)...
timeout /t 10 /nobreak >nul
echo      ✓ Дайын
echo.

REM Django серверін іске қосу
echo [3/3] Django серверін іске қосу...
echo.
echo ============================================
echo    Сервер: http://127.0.0.1:8000/
echo    Тоқтату: Ctrl+C
echo ============================================
echo.

python manage.py runserver
