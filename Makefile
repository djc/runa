.PHONY: test doc built

test: built
	python test.py

coverage: built
	coverage run test.py

doc:
	make -C doc html

built: core/personality.ll

core/personality.ll: core/personality.c
	clang -emit-llvm -S -O0 -o $@ $<
