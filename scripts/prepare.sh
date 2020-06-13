#!/usr/bin/env bash

script_path="/usr/local/sysbench1.0.14/share/sysbench/"

if [ ${1} == "read" ]
then
    run_script=${script_path}"oltp_read_only.lua"
elif [ ${1} == "write" ]
then
    run_script=${script_path}"oltp_write_only.lua"
else
    run_script=${script_path}"oltp_read_write.lua"
fi

sysbench ${run_script} \
	--mysql-host=$2 \
	--mysql-port=$3 \
	--mysql-user=cdbtune \
	--mysql-password=$4 \
	--mysql-db=sbtest \
	--db-driver=mysql \
	--tables=8 \
	--table-size=1000000 \
	--report-interval=10 \
	--threads=3 \
	--time=60 \
	prepare
