.PHONY: install test lint typecheck run audit-verify
install:
	python -m pip install -e '.[test]'
test:
	pytest --cov=control_plane --cov-report=term-missing
lint:
	ruff check src tests
typecheck:
	mypy src/control_plane
run:
	uvicorn control_plane.api:app --host 127.0.0.1 --port 8080
audit-verify:
	ds3-control-plane verify-audit
