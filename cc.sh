#!/bin/bash
cd wukong/master
pwd
printf "removed "
ls -1 *.json change* 2>/dev/null|wc -l
rm -f *.json change*

cd ../../

cd wukong/gateway
pwd
printf "removed "
ls -1 *.json device* 2>/dev/null|wc -l
rm -f *.json device*


cd udpwkpf
pwd
printf "removed "
ls -1 *.json 2>/dev/null|wc -l
rm -f *.json

cd ../../../
find -name *.pyc -print|xargs rm -f

