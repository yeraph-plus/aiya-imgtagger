@echo off
echo Building Aiya ImgTagger...
pip install pyinstaller
pyinstaller build.spec --noconfirm
echo Done. Output in build\dist\
pause
