.PHONY: test
test:
	uv venv --seed --allow-existing
	.venv/bin/pip install pytest pytest-xdist kubernetes requests jmespath jsonschema rich
	.venv/bin/pytest -svv -n auto .