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
# take the first interpreter that really runs and is 3.10+ (on Windows, "python3" is often a Microsoft Store stub)
for cand in python3 python py; do
    if command -v "$cand" &>/dev/null && "$cand" -c "import sys; assert sys.version_info >= (3, 10)" &>/dev/null; then
        PYTHON_BIN="$cand"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
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
python -m pip install --quiet -r requirements.txt
echo "      Dependencies installed."

# 4. Run automated test suite
echo "[4/5] Running the automated tests (35)..."
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
echo "  • ACC issue payloads:     $SCRIPT_DIR/out/acc_issues.json"
echo "  • Redline closure:        $SCRIPT_DIR/out/markup_closure.json"
echo "  • Structured Findings:    $SCRIPT_DIR/out/findings.json"
echo "  • Visual Overlays:        $SCRIPT_DIR/out/overlays/"
echo "========================================================================"
echo ""
echo "To launch the interactive Engineer Review Dashboard, run:"
echo "    streamlit run ui/review_app.py -- out"
echo ""
