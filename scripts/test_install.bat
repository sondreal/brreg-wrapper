@echo off
REM This script demonstrates how to test the brreg-wrapper package installation locally on Windows using UV

echo Brreg Wrapper Local Testing with UV
echo ==================================
echo.

REM Check if UV is installed
where uv > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo UV not found. Please install UV first using:
    echo curl -LsSf https://astral.sh/uv/install.ps1 ^| powershell -c -
    exit /b 1
)

REM Check if a virtual environment exists
if not exist test_venv (
    echo Creating a test virtual environment with UV...
    uv venv test_venv
)

REM Activate the virtual environment
echo Activating virtual environment...
call test_venv\Scripts\activate.bat

REM Clean existing installations
echo Cleaning any existing installations...
uv pip uninstall -y brreg-wrapper

REM Option 1: Install in development mode (editable)
echo Installing package in development mode with UV...
uv pip install -e .
echo Package installed in development mode

REM Run the sample script
echo Running sample script...
python examples\sample.py

REM Option 2: Build and install the package from the wheel
echo.
echo.
echo Building the package...
uv pip install build
python -m build

REM Install the wheel
echo Installing the built package from wheel with UV...
uv pip uninstall -y brreg-wrapper
uv pip install --find-links=dist\ brreg-wrapper
echo Package installed from wheel

REM Verify installation
echo Verifying installation:
uv pip show brreg-wrapper

REM Run same sample script with the installed package
echo Running sample script again...
python examples\sample.py

REM Deactivate virtual environment
echo Cleaning up...
call deactivate

echo.
echo All tests completed successfully!
echo You can now upload the package to PyPI if all tests passed.
echo Command to upload: python -m twine upload dist/*

pause 