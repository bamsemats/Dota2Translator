    1 @echo off
    2 setlocal
    3
    4 rem --- Configuration ---
    5 set APP_NAME=dota2-chat-translator-1.0-SNAPSHOT-jar-with-dependencies.jar
    6 set JAVA_EXE=java.exe
    7
    8 rem --- Check for Java ---
    9 "%JAVA_EXE%" -version >nul 2>&1
   10 if %errorlevel% neq 0 (
   11     echo Java Runtime Environment (JRE) not found.
   12     echo Please install a JRE (version 17 or higher) to run this application.
   13     echo For example, from: https://adoptium.net/
   14     pause
   15     exit /b 1
   16 )
   17
   18 rem --- Launch Java Application ---
   19 echo Launching Dota 2 Chat Translator...
   20 "%JAVA_EXE%" -jar "%APP_NAME%"
   21 if %errorlevel% neq 0 (
   22     echo Error: Java application failed to run.
   23     pause
   24     exit /b 1
   25 )
   26
   27 echo Application finished.
   28 endlocal
   29 exit /b 0