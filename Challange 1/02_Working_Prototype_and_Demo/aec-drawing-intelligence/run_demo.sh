#!/usr/bin/env bash
# ==============================================================================
# AEC Drawing Intelligence - One-Command Demonstration & Test Runner
# Deliverable 02: Working Prototype & Demonstration
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "    AEC DRAWING INTELLIGENCE PLATFORM - DEMO & TEST RUNNER             "
echo "========================================================================"

# 1. Check Python installation
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3.10+ is required but not found."
    exit 1
fi

echo "[1/5] Using Python: $($PYTHON_BIN --version)"

# 2. Virtual environment setup
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[2/5] Creating virtual environment at .venv..."
    $PYTHON_BIN -m venv "$VENV_DIR"
fi

# Activate venv
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
fi

# 3. Check / Install dependencies
echo "[3/5] Verifying dependencies..."
python -m pip install --quiet --upgrade pip
if ! python -c "import pymupdf, openpyxl, pydantic, cv2" &>/dev/null; then
    echo "      Installing required packages from requirements.txt..."
    python -m pip install -r requirements.txt
else
    echo "      Dependencies verified."
fi

# 4. Run automated test suite
echo "[4/5] Executing automated test suite..."
export PYTHONPATH="$SCRIPT_DIR/src"
python -m unittest discover -s "$SCRIPT_DIR/tests" -p "test_*.py"

# 5. Run end-to-end pipeline on sample project
echo "[5/5] Running end-to-end extraction and discrepancy detection..."
python -m aecdi.cli run "$SCRIPT_DIR/sample_project" --out "$SCRIPT_DIR/out"

echo ""
echo "========================================================================"
echo "    PIPELINE EXECUTION COMPLETE! OUTPUT ARTIFACTS GENERATED:           "
echo "========================================================================"
echo "  • Bluebeam Annotated Set: $SCRIPT_DIR/out/CD_Set_RevB_REVIEW.pdf"
echo "  • Excel QC Issue Log:     $SCRIPT_DIR/out/QC_Issue_Log.xlsx"
echo "  • ACC Pushpin Payloads:   $SCRIPT_DIR/out/acc_issues.json"
echo "  • Structured Findings:    $SCRIPT_DIR/out/findings.json"
echo "  • Visual Overlays:        $SCRIPT_DIR/out/overlays/"
echo "========================================================================"
echo ""
echo "To launch the interactive Engineer Review Dashboard, run:"
echo "    streamlit run ui/review_app.py -- out"
echo ""
