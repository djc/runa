Runa
====

A Python-like systems programming language.

Note: this is pre-alpha quality software. Use at your own peril.

All feedback welcome. Feel free to file bugs, requests for documentation and
any other feedback to the `issue tracker`_, `tweet me`_ or join the #runa
channel on freenode.

.. _issue tracker: https://github.com/djc/runa/issues
.. _tweet me: https://twitter.com/djco/


Installation
------------

Dependencies:

* Python 2.7
* rply (tested with 0.7.2)
* Clang (tested with 3.3 and 3.4)

So far, it has only been tested on 64-bits OS X and Linux and 32-bits Linux.
The LLVM IR targets Yosemite, this could cause warnings on older OS X. Look
at the final lines of ``runac/codegen.py`` to change the target triple.


How to get started
------------------

Type the following program into a file called ``hello.rns``:

.. code::
   
   def main():
       print('hello, world')

Make sure to use tab-based indentation; spaces are not currently supported.
Now, run the compiler to generate a binary, then run it:

.. code::
   
   djc@enrai runa $ ./runa compile hello.rns
   djc@enrai runa $ ./hello
   hello, world

Review the test cases in ``tests/`` for other code that should work.


To do before 0.1
----------------

- Core types: str, array
- Collections: list, dict, set
- Memory management
- Error handling/exceptions
- Argument handling: default args, *args, **kwargs
- Basic documentation
