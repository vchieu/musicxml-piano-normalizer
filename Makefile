PYTHON ?= python3
INPUT ?= samples/input_tempo180.xml
OUTPUT ?= output/test_output.xml

REFERENCE_INPUT ?= samples/reference_tempo90.xml
REFERENCE_OUTPUT ?= output/reference_test.xml

CHANNELS ?= 1,2

.PHONY: all output test test-reference test-all clean

all: output

output:
	@echo "Creating output folder..."
	$(PYTHON) -c "from pathlib import Path; Path('output').mkdir(parents=True, exist_ok=True)"
	@echo "Normalizing $(INPUT) -> $(OUTPUT)"
	$(PYTHON) normalize_piano_musicxml.py "$(INPUT)" "$(OUTPUT)"

test: output
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

clean:
	@echo "Removing output folder..."
	$(PYTHON) -c "import shutil; shutil.rmtree('output', ignore_errors=True)"