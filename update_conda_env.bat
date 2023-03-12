@echo off
call conda.bat activate web_scraping
conda env update --prune --file=env.yml
pause
