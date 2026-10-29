PYTHON ?= python3
INPUT ?= samples/Luu_Nien_messy.mid
OUTPUT ?= output/test_output.xml

REFERENCE_INPUT ?= samples/piano_messy.xml
REFERENCE_OUTPUT ?= output/reference_test.xml

CHANNELS ?= 1,2

.PHONY: all output test test-reference test-all web clean

all: output

output:
	@echo "Creating output folder..."
	$(PYTHON) -c "from pathlib import Path; Path('output').mkdir(parents=True, exist_ok=True)"
	@echo "Normalizing $(INPUT) -> $(OUTPUT)"
	$(PYTHON) normalize_piano_musicxml.py "$(INPUT)" "$(OUTPUT)"

test: output
	@echo "Running pytest..."
	$(PYTHON) -m pytest test_normalize.py -q
	@echo "Checking output structure: 2 parts / 1 voice per part / 2 channels"
	$(PYTHON) tests/check_output.py "$(OUTPUT)" --channels "$(CHANNELS)" --min-notes 1

test-reference:
	@echo "Creating output folder..."
	$(PYTHON) -c "from pathlib import Path; Path('output').mkdir(parents=True, exist_ok=True)"
	@echo "Normalizing reference file..."
	$(PYTHON) normalize_piano_musicxml.py "$(REFERENCE_INPUT)" "$(REFERENCE_OUTPUT)"
	@echo "Checking reference output..."
	$(PYTHON) tests/check_output.py "$(REFERENCE_OUTPUT)" --channels "$(CHANNELS)" --min-notes 1

test-all: test test-reference

web:
	$(PYTHON) -m uvicorn app:app --reload

clean:
	@echo "Removing output folder..."
	$(PYTHON) -c "import shutil; shutil.rmtree('output', ignore_errors=True)"
