#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Arne F. Meyer <arne.f.meyer@gmail.com>
# License: GPLv2

"""
    Call Matlab functions from Python

    Allows for keyword arguments and uses the subprocess module and temporary
    mat-files to exchange data with Matlab.

    Remark
    ------
    Currently, the module will only work under Linux.
"""

from __future__ import print_function

import numpy as np
import os
from os.path import join, exists, split
import tempfile
from scipy.io import savemat, loadmat
from scipy.io.matlab.mio5_params import mat_struct
import h5py
import shutil
import subprocess
import platform


def iter_struct(parent, output,
                depth=0,
                verbose=False,
                squeeze_me=True):
    # iteratively walk through a v7.3 mat file and create a scipy mat_struct

    keys = list(parent)

    if verbose:
        print(depth, keys)

    for k in keys:

        if not k.startswith('#') and not k.startswith('_'):

            child = parent[k]

            if type(child) == h5py.Group:

                if verbose:
                    print("  group", depth, k, child)

                setattr(output, k, mat_struct())
                iter_struct(child, getattr(output, k),
                            depth=depth+1,
                            verbose=verbose)

            elif type(child) == h5py.Dataset:

                if verbose:
                    print("  data set", depth, k)

                if child.dtype != np.object:
                    if squeeze_me:
                        value = np.squeeze(np.asarray(child[()]))
                    else:
                        value = np.asarray(child[()])
                    setattr(output, k, value)
                else:
                    print("skipping mat file object: {}".format(k))


def convert_mat_7_3_to_struct(mat_file,
                              var_name,
                              verbose=False,
                              squeeze_me=True):

    result = mat_struct()

    with h5py.File(mat_file, 'r') as f:

        iter_struct(f[var_name], result,
                    verbose=verbose,
                    squeeze_me=squeeze_me)

    return result


class MatlabCaller(object):
    """Wrapper for calling Matlab functions from Python"""

    def __init__(self,
                 addpath=None,
                 tempdir=None,
                 verbose=True,
                 single_comp_thread=True,
                 use_octave=False,
                 no_jvm=True,
                 no_display=True):

        self.addpath = addpath
        self.tempdir = tempdir
        self.verbose = verbose
        self.single_comp_thread = single_comp_thread
        self.use_octave = use_octave
        self.no_jvm = no_jvm
        self.no_display = no_display

    def _create_callstring(self):

        if self.use_octave:
            callstr = 'octave --no-gui --eval "'
        else:
            callstr = 'matlab -nosplash'
            if self.single_comp_thread:
                callstr += ' -singleCompThread'
            if self.no_jvm:
                callstr += ' -nojvm'
            if self.no_display:
                callstr += ' -nodisplay'
            callstr += ' -r "'

        return callstr

    def call(self, func, input_dict,
             input_order=None,
             kwarg_names=None,
             output_names=None,
             delete_inputs=False,
             pre_call=None,
             post_call=None,
             struct_as_record=False,
             squeeze_me=True,
             mat_version='7'):

        tempdir = self.tempdir
        if tempdir is None:
            tempdir = tempfile.mkdtemp()

        if not exists(tempdir):
            os.makedirs(tempdir)

        result = None
        try:
            # Basic command
            callstr = self._create_callstring()

            if self.addpath is not None:
                if isinstance(self.addpath, str):
                    callstr += "addpath('%s'); " % self.addpath
                else:
                    for pp in self.addpath:
                        callstr += "addpath('%s'); " % pp

            input_list = ''
            if input_dict is not None and len(input_dict) > 0:
                # Write data to matlab file
                infile = join(tempdir, 'input_vars.mat')
                savemat(infile, input_dict)

                callstr += "load %s;" % infile

                if input_order is None:
                    input_order = input_dict.keys()

                for k in input_order:
                    if kwarg_names is not None and k in kwarg_names:
                        input_list += "'%s',%s," % (k, k)
                    else:
                        input_list += "%s," % k
                input_list = input_list[:-1]

            if pre_call is not None:
                callstr += ' %s;' % pre_call

            output_list = ''
            if output_names is not None and len(output_names) > 0:
                # Create output argument list
                callstr += " ["
                for name in output_names:
                    callstr += name + ", "
                    output_list += "%s " % name

                callstr = callstr[:-2] + "] = "
                output_list = output_list[:-1]

            # Add function signature
            callstr += "%s(%s);" % (func, input_list)

            if post_call is not None:
                callstr += ' %s;' % post_call

            if len(output_names) > 0:
                # Save outputs
                outfile = join(tempdir, 'output_vars.mat')

                assert str(mat_version) in ['4', '6', '7', '7.3']
                callstr += ' save -v%s %s %s;' % (str(mat_version), outfile, output_list)

            # Don't forget to exit matlab
            callstr += ' exit()"'

            # Actual function call
            if self.verbose:
                print(callstr)

            cmdfile = join(tempdir, 'commands.sh')
            with open(cmdfile, 'w') as f:
                f.write('#!/bin/bash\n')
                # TODO: check display env variable first
                f.write('export DISPLAY=:0\n')
                f.write('%s\n' % callstr)

            # Delete data before calling matlab to saves memory for large array
            if delete_inputs:

                if isinstance(delete_inputs, bool):
                    # delete all input variables
                    names = input_dict.keys()
                    for name in names:
                        obj = input_dict.pop(name)
                        del obj

                elif isinstance(delete_inputs, list):
                    # list with names of the variables to be deleted
                    for name in delete_inputs:
                        obj = input_dict.pop(name)
                        del obj

            if platform.system() == 'Linux':
                subprocess.call(['bash', '-l', cmdfile])

            elif platform.system() == 'Windows':
                os.system(cmdfile)

            if len(output_names) > 0:
                # Load results
                if str(mat_version) in ['4', '6', '7']:
                    result = loadmat(outfile,
                                     struct_as_record=struct_as_record,
                                     squeeze_me=squeeze_me)
                else:
                    result = {}
                    for k in output_names:
                        result[k] = convert_mat_7_3_to_struct(outfile,
                                                              k,
                                                              squeeze_me=squeeze_me)

        finally:
            shutil.rmtree(tempdir)

        return result


if __name__ == '__main__':

    X = np.random.randn(5, 3)
    y = np.random.randn(5, 1)

    mpath = join(split(__file__)[0], '..', 'tests')
    mc = MatlabCaller(addpath=mpath)
    res = mc.call('do_something', input_dict=dict(X=X, y=y),
                  input_order=['X', 'y'], output_names=['z'])
    print(res)
