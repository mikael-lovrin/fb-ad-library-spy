@echo off
setlocal
echo === FB Ad Library Spy - installer ===
set "SRC=%~dp0skills\fb-ad-library-spy"
set "DST=%USERPROFILE%\.claude\skills\fb-ad-library-spy"
if not exist "%USERPROFILE%\.claude\skills" mkdir "%USERPROFILE%\.claude\skills"
if exist "%DST%" rmdir /s /q "%DST%"
xcopy "%SRC%" "%DST%\" /e /i /q /y >nul || goto :fail
echo [1/3] Skill copied to %DST%
python -m pip install -q -r "%~dp0requirements.txt" || goto :fail
echo [2/3] Python packages installed
python -m playwright install chromium || goto :fail
echo [3/3] Chromium for Playwright installed
where ffmpeg >nul 2>nul || echo NOTE: ffmpeg not found on PATH - video hook frames will be skipped.
echo Done. Open Claude Code anywhere and paste an Ad Library link.
exit /b 0
:fail
echo Installation failed. See the messages above.
exit /b 1
