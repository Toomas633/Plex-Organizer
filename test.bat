@echo off
setlocal

:: Define folder names
set "SOURCE_DIR=testData"
set "TARGET_DIR=testEnv"
set "TARGET_DIR_MOVIES=testEnvMovies"
set "TARGET_DIR_TV=testEnvTV"
set "PYTHON_SCRIPT=qb_organizer.py"
set "VENV_DIR=venv"

set "FULL_TARGET_DIR=%CD%\%TARGET_DIR%"
set "FULL_TARGET_DIR_MOVIES=%CD%\%TARGET_DIR_MOVIES%\movies"
set "FULL_TARGET_DIR_TV=%CD%\%TARGET_DIR_TV%\tv\Archer"
set "FULL_SCRIPT_PATH=%CD%\%PYTHON_SCRIPT%"
set "FULL_VENV_PATH=%CD%\%VENV_DIR%"

:: Check if testEnv folder exists, then delete it
if exist "%TARGET_DIR%" (
    echo Deleting %TARGET_DIR%...
    rmdir /s /q "%TARGET_DIR%"
)
if exist "%TARGET_DIR_MOVIES%" (
    echo Deleting %TARGET_DIR_MOVIES%...
    rmdir /s /q "%TARGET_DIR_MOVIES%"
)
if exist "%TARGET_DIR_TV%" (
    echo Deleting %TARGET_DIR_TV%...
    rmdir /s /q "%TARGET_DIR_TV%"
)

:: Copy testData to testEnv
if exist "%SOURCE_DIR%" (
    echo Copying %SOURCE_DIR% to %TARGET_DIR%...
    robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /e /njh /njs /ndl /nc /ns /np >nul 2>&1
    robocopy "%SOURCE_DIR%" "%TARGET_DIR_MOVIES%" /e /njh /njs /ndl /nc /ns /np >nul 2>&1
    robocopy "%SOURCE_DIR%" "%TARGET_DIR_TV%" /e /njh /njs /ndl /nc /ns /np >nul 2>&1
    echo Done.
) else (
    echo Source folder %SOURCE_DIR% not found!
    exit 1
)

:: Create the virtual environment if it doesn't exist
if not exist "%FULL_VENV_PATH%" (
    echo Creating virtual environment...
    python -m venv "%FULL_VENV_PATH%" >nul 2>&1
    if errorlevel 1 (
        echo Failed to create virtual environment!
        exit 1
    )
) else (
    echo Virtual environment already exists.
)

:: Activate the virtual environment
if exist "%FULL_VENV_PATH%\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%FULL_VENV_PATH%\Scripts\activate.bat"
    echo Installing requirements...
    pip install -r requirements.txt >nul 2>&1
) else (
    echo Virtual environment not found! Please create it first.
    exit 1
)

:: Run the Bash script using Git Bash (or WSL if available)
if exist "%FULL_SCRIPT_PATH%" (
    echo Running %PYTHON_SCRIPT%...

    python "%FULL_SCRIPT_PATH%" "%FULL_TARGET_DIR%"

    echo Running for Movies and TV directories...
    python "%FULL_SCRIPT_PATH%" "%FULL_TARGET_DIR_MOVIES%"
    python "%FULL_SCRIPT_PATH%" "%FULL_TARGET_DIR_TV%"
) else (
    echo Python script %PYTHON_SCRIPT% not found!
    exit 1
)

endlocal
