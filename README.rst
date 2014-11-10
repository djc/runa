Runa
====

A Python-like systems programming language.


Installation
------------

Dependencies:

* Python 2.7
* rply (tested with 0.7.2)
* Clang (tested with 3.3 and 3.4)

So far, it has only been tested on 64-bits OS X and Linux.


How to get started
------------------

Type the following program into a file called `hello.rns`:

.. code::
   
   def main():
       print('hello, world')

Make sure to use tab-based indentation; spaces are not currently supported.
Now, run the compiler to generate a binary, then run it:

.. code::
   
   djc@enrai runa $ ./runa compile hello.rns
   djc@enrai runa $ ./hello
   hello, world

Review the test cases in `tests/` for other code that should work.


To do before 0.1
----------------

- Basic types: bool, ints, floats
- Core types: str, array
- Collections: list, dict, set
- Duck typing
- Memory management
- Error handling/exceptions
- Iterators/generators
- Argument handling: default args, *args, **kwargs
- Basic documentation
