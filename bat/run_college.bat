@echo off
copy /Y ..\env\envcollege ..\.env
cd ..
uvicorn main:app --reload
