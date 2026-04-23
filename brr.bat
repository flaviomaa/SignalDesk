@echo off
cd /d "%~dp0"
echo .idea/>>.gitignore
git rm -r --cached .idea
git add .gitignore
git commit -m "Remove PyCharm .idea from repository"
git push origin master
pause