@echo off
copy /Y ..\env\envhome ..\.env
cd ..
uvicorn main:app --reload
