#!/bin/bash
pidfile=$1
program_name=$2

pid=$(< "$pidfile")   # a bash builtin way to say: pid=$(cat $pidfile)
if  kill -0 $pid &&
    [[ -r /proc/$pid/cmdline ]] && # find the command line of this process
    xargs -0l echo < /proc/"$pid"/cmdline  | tail -n +1 | grep "$program_name"
then
    # your application is running
    true
else
    # no such running process, or some other program has acquired that pid:
    # your pid file is out-of-date
    rm -f "$pidfile"
fi