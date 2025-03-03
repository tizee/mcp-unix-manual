.PHONEY: test

test:
	uv run python -m unittest discover
