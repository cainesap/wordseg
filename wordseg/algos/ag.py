#!/usr/bin/env python
#
# Copyright 2017 Mathieu Bernard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Adaptor Grammar

The grammar consists of a sequence of rules, one per line, in the
following format:

    [theta [a [b]]] Parent --> Child1 Child2 ...

where theta is the rule's probability (or, with the -E flag, the
Dirichlet prior parameter associated with this rule) in the generator,
and a, b (0<=a<=1, 0<b) are the parameters of the Pitman-Yor adaptor
process.

If a==1 then the Parent is not adapted. If a==0 then the Parent is
sampled with a Chinese Restaurant process (rather than the more
general Pitman-Yor process). If theta==0 then we use the default value
for the rule prior (given by the -w flag).

The start category for the grammar is the Parent category of the first
rule.

If you specify the -C flag, these trees are printed in compact format,
i.e., only cached categories are printed. If you don't specify the -C
flag, cached nodes are suffixed by a '#' followed by a number, which
is the number of customers at this table.

The -A parses-file causes it to print out analyses of the training
data for the last few iterations (the number of iterations is
specified by the -N flag).

The -X eval-cmd causes the program to run eval-cmd as a subprocess and
pipe the current sample trees into it (this is useful for monitoring
convergence).  Note that the eval-cmd is only run _once_; all the
sampled parses of all the training data are piped into it.  Trees
belonging to different iterations are separated by blank lines.

The -u and -v flags specify test-sets which are parsed using the
current PCFG approximation every eval-every iterations, but they are
not trained on.  These parses are piped into the commands specified by
the -U and -V parameters respectively.  Just as for the -X eval-cmd,
these commands are only run _once_.

The program can now estimate the Pitman-Yor hyperparameters a and b
for each adapted nonterminal.  To specify a uniform Beta prior on the
a parameter, set "-e 1 -f 1" and to specify a vague Gamma prior on the
b parameter, set "-g 10 -h 0.1" or "-g 100 -h 0.01".

If you want to estimate the values for a and b hyperparameters, their
initial values must be greater than zero.  The -a flag may be useful
here. If a nonterminal has an a value of 1, this means that the
nonterminal is not adapted.

"""

import collections
import joblib
import logging
import os
import shlex
import subprocess

from wordseg import utils


def get_grammar_files():
    """Return a list of example grammar files

    :return: a list of example grammar files bundled with wordseg

    :raise: AssertionError if no grammar files found

    """
    pkg = pkg_resources.Requirement.parse('wordseg')

    # case of 'python setup.py install'
    grammar_dir = pkg_resources.resource_filename(pkg, 'config/ag')

    # case of 'python setup.py develop' or local install
    if not os.path.isdir(grammar_dir):
        grammar_dir = pkg_resources.resource_filename(
            pkg, 'ag/config')

    assert os.path.isdir(grammar_dir), 'grammar directory not found: {}'.format(grammar_dir)

    grammar_files = [f for f in os.listdir(grammar_dir) if f.endswith('lt')]
    assert len(grammar_files) > 0, 'no *.lt files in {}'.format(grammar_dir)

    return [os.path.join(grammar_dir, f) for f in grammar_files]


def _ag(text, grammar, args, log_level=logging.ERROR):
    log = utils.get_logger(name='wordseg-ag', level=log_level)

    # generate the command to run as a subprocess
    command = '{binary} {grammar} {args}'.format(
        binary=utils.get_binary('dpseg'), grammar=grammar, args=args)

    log.debug('running "%s"', command)

    process = subprocess.Popen(
        shlex.split(command),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None)

    parses = process.communicate('\n'.join(text).encode('utf8'))
    if process.returncode:
        raise RuntimeError(
            'failed with error code {}'.format(process.returncode))

    return parses.decode('utf8').split('\n')


def yield_parses(raw_parses, ignore_firsts=0):
    """Yield parses as outputed by the ag binary

    :param sequence raw_parses: a sequence of lines (can be an opened
        file or a list). Parses are separated by an empty line.

    :yield: the current parse

    """
    nparses = 0
    parse = []

    # read input line per line, yield at each empty line
    for line in raw_parses:
        line = line.strip()
        if len(line) == 0:
            if len(parse) > 0:
                nparses += 1
                if ignore_firsts > 0 and nparses > ignore_firsts:
                    yield parse
                    parse = []
        else:
            parse.append(line)

    # yield the last parse
    if len(parse) > 0:
        if ignore_firsts > 0 and nparses > ignore_firsts:
            yield parse


def most_frequent_parse(data):
    """Counts the number of times each parse appears, and returns the
    one that appears most frequently"""
    return collections.Counter(("\n".join(d) for d in data)).most_common(1)[0][0]



def segment(text, grammar_file, njobs=1, ignore_first_parses=0, args='',
            log=utils.null_logger()):
    """Run the ag binary"""
    text = list(text)
    log.info('%s utterances loaded for segmentation', len(text))

    segmented_texts = joblib.Parallel(n_jobs=njobs, verbose=0)(
        joblib.delayed(_ag)(text, grammar_file, args, log_level=log.getEffectiveLevel())
        for _ in range(njobs))

    return most_frequent_parse(
        (parses for text in segmented_texts
         for parses in yield_parses(text, ignore_first=ignore_first_parses)))


def add_arguments(parser):
    """Add algorithm specific options to the parser"""
    parser.add_argument(
        'grammar-file', type=str, metavar='<grammar-file>',
        help='grammar file to use for segmentation, for exemple grammars see {}'
        .format(os.path.dirname(utils.get_config_files('ag', extension='.lt')[0])))

    parser.add_argument(
        '-j', '--njobs', type=int, metavar='<int>', default=1,
        help='number of parallel jobs to use, default is %(default)s')

    parser.add_argument(
        '--ignore-first-parses', type=int, metavar='<int>', default=0,
        help='discard the n first parses of each segmentation job, '
        'default is %(default)s')

    # a list of pycfg options we don't want to expose in wordseg-ag
    excluded = ['--help']

    group = parser.add_argument_group('algorithm options')
    for arg in utils.yield_binary_arguments(utils.get_binary('ag'), excluded=excluded):
        arg.add(group)


@utils.CatchExceptions
def main():
    """Entry point of the 'wordseg-dpseg' command"""
    streamin, streamout, _, log, args = utils.prepare_main(
        name='wordseg-ag',
        description=__doc__,
        add_arguments=add_arguments)

    ignored_args = ['verbose', 'quiet', 'input', 'output', 'njobs', 'grammar-file']
    ag_args = {k: v for k, v in vars(args).items() if k not in ignored_args and v}
    ag_args = ' '.join('--{} {}'.format(k, v) for k, v in ag_args.items()).replace('_', '-')

    segmented = segment(
        streamin, args.grammar_file, njobs=args.njobs,
        ignore_first_parses=args.ignore_first_parses,
        args=ag_args, log=log)

    streamout.write('\n'.join(segmented) + '\n')


if __name__ == '__main__':
    main()
