# Brreg Wrapper Development Scripts

This directory contains utility scripts for developing and testing the `brreg-wrapper` package.

## Available Scripts

- `test_install.sh`: Shell script for testing the package installation on Unix-like systems (Linux, macOS)
- `test_install.bat`: Batch script for testing the package installation on Windows

## Using the Scripts

These scripts help verify that the package installs correctly before publishing to PyPI. They:

1. Create a test virtual environment
2. Install the package in development mode
3. Run a sample script to verify functionality
4. Build a wheel package
5. Install the wheel
6. Run the sample script again with the installed package
7. Clean up

### On Unix-like Systems (Linux, macOS)

```bash
# Make the script executable
chmod +x scripts/test_install.sh

# Run the script
./scripts/test_install.sh
```

### On Windows

```cmd
scripts\test_install.bat
```

## Requirements

- Python 3.13 or later
- UV package manager (recommended) or pip
- bash shell (for Unix-like systems)
- Windows command prompt or PowerShell (for Windows)

## Notes

- The scripts use the sample script in the `examples` directory to verify functionality
- UV is used by default for faster installation and better dependency resolution
- If UV is not available, it will be installed automatically on Unix systems
- On Windows, you'll be given installation instructions if UV is not found 