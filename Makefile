install:
	python -m pip install -e ".[dev]"
data:
	python -m leakage_audit.adult_validation
benchmark:
	python -m leakage_audit.adult_validation
test:
	python -m pytest -q
audit:
	leakage-audit data/processed/adult/train.csv data/processed/adult/test.csv --target target --check-target-quality --output data/processed/adult/audit.json
wine:
	python -m leakage_audit.wine_validation --download
