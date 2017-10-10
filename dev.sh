#!/bin/bash

set -e

ag_old=../CDSwordSeg/algoComp/algos/AG/py-cfg-new/py-cfg
ag_new=./build/wordseg/algos/ag/ag
grammar=./config/ag/Colloc0_enFestival.lt
input=./test/data/prepared.txt
seed=$RANDOM

# # AG in CDSWordSeg
# resfolder=./test_ag/old
# mkdir -p $resfolder
# rm -f $resfolder/*
# $ag_old -d 101 -n 10 -E -r $seed -a 0.0001 -b 10000 \
#         -e 1 -f 1 -g 100 -h 0.01 -R -1 -P -U cat \
#         > $resfolder/output.prs $grammar < $input || exit 1

# # AG in wordseg
# resfolder=./test_ag/new
# mkdir -p $resfolder
# rm -f $resfolder/*
# $ag_new \
#     -d 0 -n 10 -E -r $seed -a 0.0001 -b 10000 \
#     -e 1 -f 1 -g 100 -h 0.01 -R -1 -P -u $input \
#     -U cat > $resfolder/output.prs $grammar < $input || exit 1

resfolder=./test_ag/ws
mkdir -p $resfolder
rm -f $resfolder/*
wordseg-ag --njobs 4 -vv \
           -d 101 -n 50 -E -r $seed -a 0.0001 -b 10000 \
           -e 1 -f 1 -g 100 -i 0.01 -R -1 -P -x 10 $grammar < $input || exit 1


exit 0