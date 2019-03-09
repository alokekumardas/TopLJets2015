#!/bin/bash

HOME=`pwd`

#set environment
CMSSW=${1}
cd ${CMSSW}/src
eval `scram r -sh`

#run the job from the home directory
cd $HOME
input=${2}
output=${3}

extraOpts=""
isMC=${4}
if [ ! -z "${MC}" ]; then
   extraOpts="${extraOpts} --mc"
fi
isPP=${5}
if [ ! -z "${isPP}" ]; then
    extraOpts="${extraOpts} --pp"
fi
opts="--in ${input} --out tto2l.root ${extraOpts}"

echo "Calling runTTto2Lselection with [${opts}]"
runTTto2Lselection ${opts}
cp -v tto2l.root ${output}

