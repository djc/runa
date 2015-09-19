Runa
====

.. image:: https://travis-ci.org/djc/runa.svg?branch=master
   :target: https://travis-ci.org/djc/runa
.. image:: https://img.shields.io/coveralls/djc/runa.svg?branch=master
   :target: https://coveralls.io/r/djc/runa?branch=master
.. image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/djc/runa
   :target: https://gitter.im/djc/runa

A Python-like systems programming language.
This means that the design borrows as much from Python
as makes sense in the context of a statically-typed, compiled language,
and tries to apply the `Zen of Python`_ to everything else.
The most important design goals for Runa are developer ergonomics
and performance.
The compiler is written in Python and targets LLVM IR;
there's no run-time.
More information, including a project rationale, can be found on the project `website`_.

Note: this is pre-alpha quality software. Use at your own peril.

All feedback welcome. Feel free to file bugs, requests for documentation and
any other feedback to the `issue tracker`_, `tweet me`_ or join the #runa
channel on freenode.

.. _Zen of Python: https://www.python.org/dev/peps/pep-0020/
.. _website: http://runa-lang.org/
.. _issue tracker: https://github.com/djc/runa/issues
.. _tweet me: https://twitter.com/djco/


Installation
------------

Dependencies:

* Python 2.7 or 3.3 (3.4 probably works as well)
* rply (tested with 0.7.2)
* Clang (tested with 3.3 and later)

The compiler is being tested on 64-bits OS X and Linux and 32-bits Linux.

Preliminary testing has been done on 64-bit Windows 7 as well. This seems
to work okay when compiling against mingw-w64, although the test suite fails
because newlines get rewritten to ``\r\n`` when using ``write()`` with
``stdout``. Compiling against the MS platform libs has been tried (through
``clang-cl``), but I have not yet been able to fix all the undefined symbol
errors.


How to get started
------------------

Type the following program into a file called ``hello.rns``:

.. code::
   
   def main():
       print('hello, world')

Make sure to use tabs for indentation.
Now, run the compiler to generate a binary, then run it:

.. code::
   
   djc@enrai runa $ ./runa compile hello.rns
   djc@enrai runa $ ./hello
   hello, world

Review the test cases in ``tests/`` for other code that should work.
