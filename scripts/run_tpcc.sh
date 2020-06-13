#!/usr/bin/env bash

# $1 IP
# $2 port
# $3 passwd
# $4 filename


# -w: warehouse num
# -c: thread nums
# -r: warmup time
# -l: lasting time
# -i: report interval
# -f: report file name

tpcc_start -h${1} -d tpcc_test -P ${2}  -uroot -p${3} -w 1000 -c 600 -r 10 -l 150 -i 5 > ${4}
