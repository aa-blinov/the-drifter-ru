@echo off
chcp 65001 >nul
rem The Drifter RU installer. Keep this file next to the scripts folder.
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Не найден Python 3. Поставьте его с https://www.python.org/downloads/
  echo и при установке отметьте "Add python.exe to PATH".
  pause
  exit /b 1
)

echo [1/3] Зависимости установщика
%PY% -m pip install --quiet -r requirements.txt || goto :fail

echo [2/3] Пиксельные шрифты Ark Pixel и Play (SIL OFL 1.1)
%PY% scripts\fetch_fonts.py || goto :fail

echo [3/3] Установка в игру
%PY% scripts\install.py %* || goto :fail

echo.
echo Готово. В игре: Options - Language - Русский.
pause
exit /b 0

:fail
echo.
echo Установка не завершилась. Игра не изменена: оригинальные файлы лежат в _ru_backup.
pause
exit /b 1
