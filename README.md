# yumtools
Tools to handle yum  package dependencies

This is a collection of two programs used to list dependencies of packages in a list of yum repositories.

The process was divided in two steps. The were two reasons for that (1) when this project was started, yum did
not have a documented and stable API to interact with yum repositories from Python, and (2) running yum directly
from python created import problems with yum, which is in turn written in Python. The cleaner solution was to
use a shell script to gather all the data from the yum repositories and a Python program to process and format
the output.

For example, to generate the list of dependencies of the packages in the repositories 'myrepo-production'
and 'myrepo-testing' type:

./yumdeps.csh myrepo-production myrepo-testing

This will generate three files: pkg.lsit (list of packages), pkg.info (package information) and
pkg.dep (package dependencies).

Then yumdeps.py can be used to generate the output in text, csv and mediawii formats.

./yumdeps.py -o text
./yumdeps.py -o csv
./yumdeps.py -o wiki

The csv output is intended to be used in combination with spreadsheet filters.
