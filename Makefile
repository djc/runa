.PHONY: test doc

test:
	python test.py

coverage:
	coverage run test.py

doc:
	make -C doc html
