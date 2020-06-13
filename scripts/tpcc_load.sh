#!/usr/bin/env bash

# $1 IP
# $2 port
# $2 passwd
mysqladmin -h ${1} -u root -p${2} create tpcc_test

tpcc_load -h${1} -P ${2} -d tpcc_test -uroot -p${3}  -w 1000
