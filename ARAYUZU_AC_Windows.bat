@echo off
chcp 65001 >nul
setlocal
title Katmanli puanlama - arayuz
cd /d "%~dp0"
set PYTHONUTF8=1

echo.
echo  Katmanli cok modelli puanlama - arayuz baslatiliyor
echo  (ilk calistirmada kurulum birkac dakika surer; bu pencereyi kapatmayin)
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo [1/3] uv kuruluyor...
  powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>nul
if errorlevel 1 goto hata_uv

echo [2/3] Python ortami hazirlaniyor...
uv sync --extra ui --extra spelling
if errorlevel 1 goto hata

echo [3/3] Arayuz aciliyor: http://127.0.0.1:8501
echo  Kapatmak icin bu pencerede Ctrl+C ya da pencereyi kapatin.
uv run scoring ui --open
goto son

:hata_uv
echo.
echo HATA: uv kurulamadi. https://docs.astral.sh/uv/ adresinden elle kurup bu dosyayi yeniden calistirin.
pause
exit /b 1

:hata
echo.
echo HATA: kurulum tamamlanamadi. Yukaridaki mesaji kaydedip gonderin.
pause
exit /b 1

:son
endlocal
