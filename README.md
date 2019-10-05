# yumtools
Tools to handle yum  package dependencies

This is a collection of two programs used to list dependencies of packages in a list of yum repositories.

The process was divided in two steps. The were two reasons for that (1) when this project was started, yum did
not have a documented and stable API to interact with yum repositories from Python, and (2) running yum directly
from python created import problems with yum, which is in turn written in Python. The cleaner solution was to
use a shell script to gather all the data from the yum repositories and a Python program to process and format
the output.
