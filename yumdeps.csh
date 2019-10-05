#!/bin/csh -f
unalias *

onintr clean

# File names
set tmp_list="/tmp/yumdepsl-`date +%Y%M%d%H%M%S`"
set tmp_info="/tmp/yumdepsi-`date +%Y%M%d%H%M%S`"
set tmp_dep="/tmp/yumdepsd-`date +%Y%M%d%H%M%S`"
set tmp_errors="/tmp/yumdepse-`date +%Y%M%d%H%M%S`"
set pkg_list = './pkg.list'
set pkg_info = './pkg.info'
set pkg_dep = './pkg.dep'
set yum_errors = './pkg.errors'

# Get packages to seach for
set repo_list = ''
if ($#argv > 0) then
    set repo_list = $argv[1]
    shift argv
    foreach repo ($argv)
	set repo_list = $repo_list'|'$repo
    end
endif

if ($repo_list == '') then
    echo 'Usage: yumdeps.csh repository [repository ...]'
    exit 1
endif

# Get the list of packages
echo "getting package list..."
yum list | egrep "$repo_list" | awk '{print $1}' > $tmp_list

# Get package information
cp -f /dev/null $tmp_info
echo "getting package info..."
foreach pkg (`cat $tmp_list`)
    (yum info $pkg >> $tmp_info) >& $tmp_errors
end

# Get package dependencies
cp -f /dev/null $tmp_dep
echo "getting package dependencies..."
foreach pkg (`cat $tmp_list`)
    (yum deplist $pkg >> $tmp_dep) >>& $tmp_errors
end

# Save temporary files
mv -f $tmp_list $pkg_list
mv -f $tmp_info $pkg_info
mv -f $tmp_dep $pkg_dep
if (`wc -l $tmp_errors` == 0) then
    rm -f $tmp_errors
else
    mv -f $tmp_errors $yum_errors
endif

# Remove temporary files
clean:
echo "aborting..."
rm -f $tmp_list
rm -f $tmp_info
rm -f $tmp_dep
rm -f $tmp_errors
