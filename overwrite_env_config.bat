@echo off
call conda.bat activate web_scraping
conda env export > env.yml
pause
