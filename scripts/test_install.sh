#!/bin/bash
# This script demonstrates how to test the brreg-wrapper package installation locally using UV

set -e  # Exit immediately if a command exits with a non-zero status

echo "Brreg Wrapper Local Testing with UV"
echo "=================================="
echo

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "⚠️ UV not found. Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add UV to the current session's PATH
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Check if a virtual environment exists
if [ ! -d "test_venv" ]; then
    echo "🔧 Creating a test virtual environment with UV..."
    uv venv test_venv
fi

# Activate the virtual environment
echo "🔧 Activating virtual environment..."
# Use different activation depending on the platform
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    source test_venv/Scripts/activate
else
    source test_venv/bin/activate
fi

# Clean existing installations
echo "🧹 Cleaning any existing installations..."
uv pip uninstall -y brreg-wrapper || true

# Option 1: Install in development mode (editable)
echo "📦 Installing package in development mode with UV..."
uv pip install -e .
echo "✅ Package installed in development mode"

# Run the sample script
echo "🚀 Running sample script..."
python examples/sample.py

# Option 2: Build and install the package from the wheel
echo -e "\n\n"
echo "📦 Building the package..."
uv pip install build
python -m build

# Install the wheel
echo "📦 Installing the built package from wheel with UV..."
uv pip uninstall -y brreg-wrapper
uv pip install --find-links=dist/ brreg-wrapper
echo "✅ Package installed from wheel"

# Verify installation
echo "ℹ️ Verifying installation:"
uv pip show brreg-wrapper

# Run same sample script with the installed package
echo "🚀 Running sample script again..."
python examples/sample.py

# Deactivate virtual environment
echo "🔧 Cleaning up..."
deactivate

echo -e "\n✅ All tests completed successfully!"
echo "You can now upload the package to PyPI if all tests passed."
echo "Command to upload: python -m twine upload dist/*" 