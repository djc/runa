.PHONY: test

test:
	python test.py

coverage:
	coverage run test.py
