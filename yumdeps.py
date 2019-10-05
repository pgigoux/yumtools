#!/usr/bin/env python
"""
Find yum dependencies

This program prints the list of dependencies of all packages listed in the 'pkg.info' file
in three different output formats: text, csv, and wikimedia.

The program reads the package information and package dependencies from two text files that
are constructed using "yum list", "yum info" and "yum deplist". A shell script is used to
automate this process and also to restrict the repositories to look for packages.

The original idea was to call the yum API directly, but the API is not documented and could
change at any time. Running yum directly from this program also didn't work because it interfered
with the yum package dependencies. Parsing the yum output was the simplest approach.
"""
import sys
import logging
from argparse import ArgumentParser

# Keywords used to parse the package information file.
# They are also used as indices in the package information dictionary.
KEY_NAME = 'Name'
KEY_ARCH = 'Arch'
KEY_VERSION = 'Version'
KEY_RELEASE = 'Release'
KEY_REPOSITORY = 'Repo'
KEY_SUMMARY = 'Summary'
KEY_INFO_LIST = [KEY_NAME, KEY_ARCH, KEY_VERSION, KEY_RELEASE, KEY_REPOSITORY, KEY_SUMMARY]

# Keywords used to parse the dependency file
KEY_PACKAGE = 'package:'
KEY_DEPENDENCY = 'dependency:'
KEY_PROVIDER = 'provider:'
KEY_DEP_LIST = [KEY_PACKAGE, KEY_DEPENDENCY, KEY_PROVIDER]

# String use to initialize undefined strings
UNDEFINED = 'undefined'

# String used to flag internal packages and dependencies
INTERNAL = 'internal'
EXTERNAL = 'external'

# Output options
OUT_TEXT = 'text'
OUT_CSV = 'csv'
OUT_WIKI = 'wiki'
OUT_SUMMARY = OUT_TEXT + '|' + OUT_CSV + '|' + OUT_WIKI

# Default input file name root
DEFAULT_ROOT = 'pkg'


class PkgDep:
    """
    This class is used to encapsulate all the details how the package/dependency information
    is stored in memory.

    The package and dependency information is stored two dictionaries. Both dictionaries are
    indexed by the package name followed by the architecture separated by a dot (e.g. VDCT.i686).
    This is to ensure a unique key is used to access elements in both dictionaries.

    The "pkg" dictionary is used to store information about the package itself. Each dictionary
    entry is a six element tuple containing the package name, architecture, version number (or string),
    release number (or string), repository (e.g. gemini-production/7/x86_64) and summary.
    The summary will be truncated if it uses more than one line.

    The "dep" dictionary is used to store the dependency information for each package. Each dictionary
    entry is a dictionary indexed by the dependency name (e.g. cfitsio). The list will be empty if the
    package has no dependencies.

    Each dependency entry will contain a list of providers, and each provider will be described
    by a two element tuple containing the provider name and architecture. The provider name follows
    the same naming convention as "pkg" and "dep" keys.

    Packages listed in the "pkg" dictionary are considered "internal". Dependencies containing at
    least one provider listed in the "pkg" dictionary are also considered "internal".
    """

    def __init__(self):
        self.pkg = {}
        self.dep = {}

    def add_package(self, pkg_name, arch, version, release, repository, summary):
        """
        Add package information and initialize dependency information.
        If the package already exists, it is overwritten.
        :param pkg_name: package name
        :type pkg_name: str
        :param arch: architecture
        :type arch: str
        :param version: version
        :type version: str
        :param release: release number
        :type release: str
        :param repository: repository providing the package
        :type repository: str
        :param summary: one line description of the package
        :type summary: str
        :return: None
        """
        logging.debug('add_package ' + pkg_name)
        if pkg_name not in self.pkg:
            self.pkg[pkg_name] = {KEY_ARCH: arch, KEY_VERSION: version, KEY_RELEASE: release,
                                  KEY_REPOSITORY: repository, KEY_SUMMARY: summary}
            self.dep[pkg_name] = {}
        else:
            logging.warning('package ' + pkg_name + ' already exists, ignored')

    def add_dependency(self, pkg_name, dep_name):
        """
        Add dependency for a given package.
        :param pkg_name: package name
        :type pkg_name: str
        :param dep_name: dependency name
        :type dep_name: str
        :return: None
        """
        logging.debug('add_dependency ' + pkg_name + ' ' + dep_name)
        if pkg_name in self.dep:
            if dep_name not in self.dep[pkg_name]:
                self.dep[pkg_name].update({dep_name: []})
            else:
                logging.warning('dependency ' + dep_name + ' already exists for package ' + pkg_name)
        else:
            self.dep[pkg_name] = {dep_name: []}

    def add_provider(self, pkg_name, dep_name, provider, version):
        """
        Add provider for a given package and dependency.
        A dependency can be provided by more than one package (e.g. different architectures).
        The provider will be the name of the package that provides the dependency.
        :param pkg_name: package name
        :type pkg_name: str
        :param dep_name: dependency name
        :type dep_name: str
        :param provider: provider name (package)
        :type provider: str
        :param version: provider version
        :type version: str
        :raise ValueError: if package or dependency are nor found.
        ::return: None
        """
        if pkg_name in self.dep:
            if dep_name in self.dep[pkg_name]:
                # r_name, r_repo = DepDict._extract_version_and_repo(version)
                self.dep[pkg_name][dep_name].append((provider, version))
                logging.debug('adding provider ' + provider)
            else:
                raise ValueError('dependency ' + dep_name + ' for package ' + pkg_name + ' does not exist')
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_arch(self, pkg_name):
        """
        Return the package architecture.
        The architecture could be UNDEFINED if it was not defined (unlikely).
        :param pkg_name: package name
        :type pkg_name: str
        :raise ValueError: if package is not found
        :return: package architecture
        :rtype: str
        """
        if pkg_name in self.pkg:
            return self.pkg[pkg_name][KEY_ARCH]
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_version(self, pkg_name):
        """
        Return the package version (e.g. '2.5.1271')
        :param pkg_name: package name
        :type pkg_name: str
        :raise ValueError: if package is not found
        :return: package version
        :rtype: str
        """
        if pkg_name in self.pkg:
            return self.pkg[pkg_name][KEY_VERSION]
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_release(self, pkg_name):
        """
        Return the package release number (e.g. '6', '14.el7.gemini', etc.)
        :param pkg_name: package name
        :type pkg_name: str
        :raise ValueError: if package is not found
        :return: package version
        :rtype: str
        """
        if pkg_name in self.pkg:
            return self.pkg[pkg_name][KEY_RELEASE]
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_repository(self, pkg_name):
        """
        Return the package repository (e.g. 'gemini-production/7/x86_64')
        :param pkg_name: package name
        :type pkg_name: str
        :raise ValueError: if package is not found
        :return: package version
        :rtype: str
        """
        if pkg_name in self.pkg:
            return self.pkg[pkg_name][KEY_REPOSITORY]
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_summary(self, pkg_name):
        """
        Return the package one line summary.
        :param pkg_name: package name
        :type pkg_name: str
        :raise ValueError: if package is not found
        :return: package version
        :rtype: str
        """
        if pkg_name in self.pkg:
            return self.pkg[pkg_name][KEY_SUMMARY]
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_dependency_list(self, pkg_name):
        """
        Return the (sorted) list of dependencies for a given package.
        The list can be empty if the package has no dependencies.
        :param pkg_name: package name
        :type pkg_name: str
        :raise ValueError: if package is not found
        :return: dependency list
        :rtype: list
        """
        if pkg_name in self.dep:
            return sorted(self.dep[pkg_name])
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def get_provider_list(self, pkg_name, dep_name):
        """
        Return the list of providers for a given package and dependency.
        There should be at least one provider for each dependency.
        The providers are returned as a list of tuples; the first element of the tuple is the
        provider name and the second one the provider version
        :param pkg_name: package name
        :type pkg_name: str
        :param dep_name: dependency name
        :type dep_name: str
        :param dep_name:
        :raise ValueError: if package or dependency are not found
        :return: list of providers (tuple)
        :rtype: list
        """
        if pkg_name in self.dep:
            if dep_name in self.dep[pkg_name]:
                return self.dep[pkg_name][dep_name]
            else:
                raise ValueError('package ' + pkg_name + ' does not exist')
        else:
            raise ValueError('dependency ' + dep_name + ' for package ' + pkg_name + ' does not exist')

    def internal_package(self, pkg_name):
        """
        Check whether a package exists
        :param pkg_name:
        :return: True if the package is defined, False otherwise
        :rtype: bool
        """
        return pkg_name in self.pkg

    def internal_dependency(self, pkg_name, dep_name):
        found = False
        for p_name, p_version in self.get_provider_list(pkg_name, dep_name):
            if self.internal_package(p_name):
                found = True
                break
        return found

    def package_count(self):
        for p in sorted(self.pkg):
            print(p)
        return len(self.pkg)

    def dependency_count(self, pkg_name):
        if pkg_name in self.dep:
            return len(self.dep[pkg_name])
        else:
            raise ValueError('package ' + pkg_name + ' does not exist')

    def provider_count(self, pkg_name, dep_name):
        if pkg_name in self.dep:
            if dep_name in self.dep[pkg_name]:
                return len(self.dep[pkg_name][dep_name])
            else:
                raise ValueError('package ' + pkg_name + ' does not exist')
        else:
            raise ValueError('dependency ' + dep_name + ' for package ' + pkg_name + ' does not exist')

    def print_packages_and_dependencies(self):
        """
        Print the package/dependency/provider to the standard output.
        Used for debugging.
        :return:
        """
        print('\n' + '-' * 80)
        for pkg_name in sorted(self.pkg):
            print('Package {} [{}] [{}] [{}] [{}] [{}]'.format(pkg_name,
                                                               self.get_version(pkg_name),
                                                               self.get_release(pkg_name),
                                                               self.get_arch(pkg_name),
                                                               self.get_repository(pkg_name),
                                                               self.get_summary(pkg_name)))
            for dep_name in self.get_dependency_list(pkg_name):
                print(' ' * 2 + dep_name)
                for p_name, p_version in self.get_provider_list(pkg_name, dep_name):
                    flag = ' yes' if self.internal_package(p_name) else ' no'
                    print(' ' * 4 + '[' + p_name + ', ' + p_version + ']' + flag)


def split_info_line(line):
    """
    Split package info line into (meaningful) words.
    This routine looks for lines containing the package name, architecture, version, release,
    repository and summary information.
    It returns the keyword found and its value, or (None, None) if the line does not contain
    any of the expected keywords.
    :param line: input line
    :type line: str
    :return: tuple with the keyword and value. (None, None) otherwise.
    :rtype: tuple
    """
    words = line.split(':')
    key = words[0].strip()
    if key in KEY_INFO_LIST:
        return key, words[1].strip()
    else:
        return None, None


def split_dep_line(line):
    """
    Split package dependency line into (meaningful) words.
    This routine looks for lines containing package, dependency or provider information.
    It always returns a three element tuple containing the relevant information.
    - Package line: keyword (KEY_PACKAGE), package name and version.
    - Dependency line: keyword (KEY_DEPENDENCY), dependency name and None.
    - Provider: keyword (KEY_PROVIDER), provider name and provider version.
    :param line: input line
    :type line: str
    :return: tuple with relevant information. (None, None, None) otherwise.
    :rtype: tuple
    """
    words = line.split()
    key = words[0].strip()
    if key == KEY_PACKAGE:
        return key, words[1].strip(), words[2].strip()
    elif key == KEY_DEPENDENCY:
        return key, words[1].strip(), None
    elif key == KEY_PROVIDER:
        return key, words[1].strip(), words[2].strip()
    else:
        return None, None, None


def parse_info_file(f, dep):
    """
    Parse a file containing package information.
    This file is generated by another program that runs 'yum info' over a list of packages.
    The package information is scattered in several lines. This function assumes that the
    package name will always come first.
    :param f: info file
    :type f: file
    :param dep: package/dependency object
    :type dep: PkgDep
    :return: updated package/dependency object
    :rtype: PkgDep
    """

    # Initialize values. Only the package name needs to be initialized at this
    # point, but initializing all variables keeps PyCharm happy :)
    pkg_name = UNDEFINED
    pkg_arch = UNDEFINED
    pkg_version = UNDEFINED
    pkg_release = UNDEFINED
    pkg_repository = UNDEFINED
    pkg_summary = UNDEFINED

    for line in f:

        key, name = split_info_line(line)
        # print key, name

        if key == KEY_NAME:
            logging.debug('found package ' + name)

            # Add "previous" package information.
            # The package name will be UNDEFINED the first time.
            if pkg_name != UNDEFINED:
                dep.add_package(pkg_name + '.' + pkg_arch, pkg_arch, pkg_version,
                                pkg_release, pkg_repository, pkg_summary)
            pkg_name = name

            # Reset values
            pkg_arch = UNDEFINED
            pkg_version = UNDEFINED
            pkg_release = UNDEFINED
            pkg_repository = UNDEFINED
            pkg_summary = UNDEFINED

        elif key == KEY_VERSION:
            logging.debug('  found version ' + name)
            pkg_version = name
        elif key == KEY_RELEASE:
            logging.debug('  found release ' + name)
            pkg_release = name
        elif key == KEY_ARCH:
            logging.debug('  found arch ' + name)
            pkg_arch = name
        elif key == KEY_REPOSITORY:
            logging.debug('  found repo ' + name)
            pkg_repository = name
        elif key == KEY_SUMMARY:
            logging.debug('  found summary ' + name)
            pkg_summary = name

    # Output the last package
    dep.add_package(pkg_name + '.' + pkg_arch, pkg_arch, pkg_version,
                    pkg_release, pkg_repository, pkg_summary)

    return dep


def parse_dep_file(f, dep):
    """
    Parse dependency file for package, dependency or provider definitions.
    This file is generated by another program that runs 'yum deplist' over a list of packages.
    This function assumes that the package name will always come first.
    :param f: dependency file
    :type f: file
    :param dep: package/dependency object
    :type dep: PkgDep
    :return: updated package/dependency object
    :rtype: PkgDep
    """
    pkg_name = UNDEFINED
    dep_name = UNDEFINED

    for line in f:

        key, name, version = split_dep_line(line)

        if key == KEY_PACKAGE:
            logging.debug('found package ' + name + ' ' + name)
            # dep.add_package(name, name)
            pkg_name = name
        elif key == KEY_DEPENDENCY:
            logging.debug('  found dependency ' + name)
            dep.add_dependency(pkg_name, name)
            dep_name = name
        elif key == KEY_PROVIDER:
            logging.debug('    found provider ' + pkg_name + ' ' + dep_name + ' ' + name + ' ' + version)
            dep.add_provider(pkg_name, dep_name, name, version)

    return dep


def parse_files(info_file_name, dep_file_name):
    """
    Parse the package information and dependency files.
    Returns the object containing all these information.
    :param info_file_name: package information file name
    :type info_file_name: str
    :param dep_file_name: package dependency file name
    :type dep_file_name: str
    :return: package/dependency object
    :rtype: PkgDep
    """
    dep = PkgDep()

    with open(info_file_name, 'r') as f_info, open(dep_file_name, 'r') as f_dep:
        dep = parse_info_file(f_info, dep)
        dep = parse_dep_file(f_dep, dep)

    return dep


def get_dep_list(dep, pkg_name, include_all):
    """
    Return the package dependency list taking into account all the dependencies
    should be included or only those that are internal (included in the package
    list).
    :param dep: package/dependency object
    :type dep: PkgDep
    :param pkg_name: package name
    :type pkg_name: str
    :param include_all: include all dependencies?
    :type include_all: bool
    :return dependency list
    :rtype: list
    """
    d_list = dep.get_dependency_list(pkg_name)
    if not include_all:
        d_list = [d for d in d_list if dep.internal_dependency(pkg_name, d)]
    return d_list


# def output_text(dep, print_all):
#     """
#     Print package dependencies in plain text format. This is very similar to the output
#     from print_packages_and_dependencies, but here not internal dependencies are
#     filtered out.
#     :param dep: package/dependency object
#     :type dep: PkgDep
#     :param print_all: dependencies
#     :type print_all: bool
#     :return: None
#     """
#     for pkg_name in sorted(dep.pkg):
#         print 'Package {} [{}] [{}] [{}] [{}] [{}]'.format(pkg_name,
#                                                            dep.get_version(pkg_name),
#                                                            dep.get_release(pkg_name),
#                                                            dep.get_arch(pkg_name),
#                                                            dep.get_repository(pkg_name),
#                                                            dep.get_summary(pkg_name))
#         for dep_name in dep.get_dependency_list(pkg_name):
#             if not print_all and not dep.internal_dependency(pkg_name, dep_name):
#                 continue
#             print ' ' * 2 + dep_name
#             for p_name, p_version in dep.get_provider_list(pkg_name, dep_name):
#                 flag = ' ' + INTERNAL if dep.internal_package(p_name) else ''
#                 print ' ' * 4 + '[' + p_name + ', ' + p_version + ']' + flag


def output_text(dep, print_all):
    """
    Print package dependencies in plain text format. This is very similar to the output
    from print_packages_and_dependencies, but here not internal dependencies are
    filtered out.
    :param dep: package/dependency object
    :type dep: PkgDep
    :param print_all: dependencies
    :type print_all: bool
    :return: None
    """
    for pkg_name in sorted(dep.pkg):

        # Print package information
        print('Package {} [{}] [{}] [{}] [{}] [{}]'.format(pkg_name,
                                                           dep.get_version(pkg_name),
                                                           dep.get_release(pkg_name),
                                                           dep.get_arch(pkg_name),
                                                           dep.get_repository(pkg_name),
                                                           dep.get_summary(pkg_name)))

        # Get (effective) dependency list for the current package
        dep_list = get_dep_list(dep, pkg_name, print_all)
        if len(dep_list) == 0:
            continue

        # Print all dependency and provider information
        for dep_name in dep_list:
            print(' ' * 2 + dep_name)
            for p_name, p_version in dep.get_provider_list(pkg_name, dep_name):
                flag = ' ' + INTERNAL if dep.internal_package(p_name) else ''
                print(' ' * 4 + '[' + p_name + ', ' + p_version + ']' + flag)


def output_csv(dep, print_all):
    """
    Print package dependencies in plain csv format, one dependency per line.
    Non internal dependencies are filtered out.
    :param dep: package/dependency object
    :type dep: PkgDep
    :param print_all: dependencies
    :type print_all: bool
    :return: None
    """
    print('Package name,Version,Release,Architecture,Repository,Summary,Dependency,Providers... (*) internal provider')
    for pkg_name in sorted(dep.pkg):
        pkg_line = '{},{},{},{},{},{}'.format(pkg_name,
                                              dep.get_version(pkg_name),
                                              dep.get_release(pkg_name),
                                              dep.get_arch(pkg_name),
                                              dep.get_repository(pkg_name),
                                              dep.get_summary(pkg_name).replace(',', ' '))

        # Get the (effective) dependency list for the current package
        dep_list = get_dep_list(dep, pkg_name, print_all)
        if len(dep_list) == 0:
            print(pkg_line + ',---')
            continue

        # Print dependency and provider information
        for dep_name in dep_list:
            line = pkg_line + ',' + dep_name
            for p_name, p_version in dep.get_provider_list(pkg_name, dep_name):
                flag = ',(*)' if dep.internal_package(p_name) else ','
                line += ',' + p_name + ',' + p_version + flag
            print(line)


def output_wiki(dep, print_all):
    """
    Print package dependencies in plain WikiMedia format.
    Non internal dependencies are filtered out.
    :param dep: package/dependency object
    :type dep: PkgDep
    :param print_all: dependencies
    :type print_all: bool
    :return: None
    """
    # Header
    print('{| class="wikitable"')
    print('! # || Package || Version|| Repository || Dependency || Provider || Version || Repository')
    print('|-')

    # Compute the number of rows per package.
    # This information is needed before printing the output.
    row_span = {}
    for pkg_name in sorted(dep.pkg):
        row_span[pkg_name] = 0
        dep_list = get_dep_list(dep, pkg_name, print_all)
        for dep_name in dep_list:
            row_span[pkg_name] += dep.provider_count(pkg_name, dep_name)
        row_span[pkg_name] = max(row_span[pkg_name], 1)

    pkg_count = 1
    for pkg_name in sorted(dep.pkg):

        # Print package name and architecture.
        # The row span should be the same for both.
        # The anchor to the package entry is included at this point.
        print('| rowspan="' + str(row_span[pkg_name]) + '" | ' + str(pkg_count))
        print('| rowspan="' + str(row_span[pkg_name]) + '" | ' + '<span id="' + pkg_name + '">' + pkg_name + '</span>')
        print('| rowspan="' + str(row_span[pkg_name]) + '" | ' + dep.get_version(pkg_name))
        print('| rowspan="' + str(row_span[pkg_name]) + '" | ' + dep.get_repository(pkg_name))
        pkg_count += 1

        # Get the (effective) dependency list for the current package.
        # Print default output for a package with no dependencies.
        dep_list = get_dep_list(dep, pkg_name, print_all)
        len_dep_list = len(dep_list)
        if len_dep_list == 0:
            print('| ---')
            print('| ---')
            print('| ---')
            print('| ---')
            print('|-')
            continue

        # Loop over all the dependencies.
        # The row span for each dependency will be the number of providers.
        # Print the provider name, version and repository.
        # Non-internal providers won't have a repository (and all other properties).
        for dep_name in dep_list:
            print('| rowspan="' + str(dep.provider_count(pkg_name, dep_name)) + '" | ' + dep_name)
            for p_name, p_version in dep.get_provider_list(pkg_name, dep_name):
                try:
                    p_repository = dep.get_repository(p_name)
                except ValueError:
                    p_repository = ''
                if dep.internal_package(p_name):
                    p_name = '[[#' + p_name + '|' + p_name + ']]'
                print('| ' + p_name)
                print('| ' + p_version)
                print('| ' + p_repository)
                print('|-')
    print('|}')


def get_args(argv):
    parser = ArgumentParser(epilog='')

    parser.add_argument('-i', '--input-root',
                        action='store',
                        dest='input',
                        default=DEFAULT_ROOT,
                        help='Input file root name default=(' + DEFAULT_ROOT + ')')

    parser.add_argument('-o', '--output-format',
                        action='store',
                        dest='output',
                        choices=[OUT_TEXT, OUT_CSV, OUT_WIKI],
                        default=OUT_WIKI,
                        help='Output format default=(' + OUT_TEXT + ')')

    parser.add_argument('-a', '--all',
                        action='store_true',
                        dest='all',
                        default=False,
                        help='Print all dependencies (default=False)')

    return parser.parse_args(argv[1:])


if __name__ == '__main__':

    args = get_args(sys.argv)
    # print args

    logging.basicConfig(level=logging.ERROR)

    p_dep = parse_files(args.input + '.info', args.input + '.dep')

    if args.output == OUT_TEXT:
        output_text(p_dep, args.all)
    elif args.output == OUT_CSV:
        output_csv(p_dep, args.all)
    elif args.output == OUT_WIKI:
        output_wiki(p_dep, args.all)
    else:
        raise ValueError('Unknown output option')
