chcp 65001 >nul
@echo off
echo Запуск парсинга...
python build.py

echo Копирование в docs...
rmdir /s /q docs
xcopy output docs /E /I

echo Отправка на GitHub...
git add docs/
git commit -m "Авто-обновление: %date% %time%"
git push

echo Готово!
pause