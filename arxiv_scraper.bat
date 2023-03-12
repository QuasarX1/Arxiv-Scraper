@echo off
call conda.bat activate web_scraping
python .\arxiv_scraper.py
pause
