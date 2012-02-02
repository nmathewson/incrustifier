#!/usr/bin/python
# incrustify.py -- Copyright 2012 Nick Mathewson
#
# Copyright 2012 Nick Mathewson. You may do absolutely anything with
# this program that copyright law would otherwise restrict, so long as
# you include this paragraph in all redistributed or modified copies
# and in all derivative works. There is ABSOLUTELY no warranty.

import re
import difflib
import subprocess
import tempfile

class OptionType:
    def getValues(self):
        return None
class Alternative(OptionType):
    def __init__(self, values):
        self.values = values[:]
    def getValues(self):
        return self.values
class Number(OptionType):
    pass
class String(OptionType):
    pass
class NumberRange(OptionType):
    def __init__(self, rng):
        self.rng = rng
    def getValues(self):
        return self.rng

OVERRIDE_TYPES = dict(
    indent_columns=Alternative([2,4,8]),
    indent_continue=Alternative([2,4,8]),
    indent_with_tabs=Alternative([0,1,2]),
    indent_switch_case=Alternative([0,2,3,4,8]),
    indent_case_brace=Alternative([0,2,4,8]),
    indent_label=Alternative([-8,-6,-4,-2,0,2,4,8]),
    indent_paren_close=Alternative([0,1,2]),
    align_var_def_star_style=Alternative([0,1,2]),
    align_var_def_amp_style=Alternative([0,1,2]),

    code_width=Alternative([72,79,80,100,120]),
    nl_max=Alternative([0,1,2,3,4]),
    nl_after_func_proto=Alternative([0,1,2,3,4]),
    nl_after_func_proto_group=Alternative([0,1,2,3,4]),
    nl_after_func_body=Alternative([0,1,2,3,4]),
    nl_after_func_body_one_liner=Alternative([0,1,2,3,4]),
    nl_before_block_comment=Alternative([0,1,2,3,4]),
    nl_before_c_comment=Alternative([0,1,2,3,4]),
    nl_before_cpp_comment=Alternative([0,1,2,3,4]),

    cmt_width=Alternative([72,79,80,100,120]),
    cmt_reflow_mode=Alternative([0,1,2]),
    cmt_sp_before_star_cont=Alternative([0,1,2,4]),
    cmt_sp_after_star_cont=Alternative([0,1,2,4])
)

def parseCfgLines(lines):
    output = []
    options = {}
    option_re = re.compile(r'^(\S+)\s*=\s*(\S+)\s*#\s*(\S+)$')
    for ln in lines:
        ln = ln.strip()
        if ln == "":
            output.append(["SPACE", ln])
            continue
        elif ln[0] == '#':
            if ln.startswith('##'):
                continue
            output.append(["COMMENT", ln])
            continue
        m = option_re.match(ln)
        if not m:
            print "???>", ln
            output.append(["???", ln])
            continue
        name, default, tp = m.groups()
        if name in OVERRIDE_TYPES:
            t = OVERRIDE_TYPES[name]
        elif '/' in tp:
            t = Alternative(tp.split("/"))
        elif tp == 'number':
            t = Number()
        elif tp == 'string':
            t = String()
        else:
            print "I have no idea how to handle",tp
        output.append(["OPTION", ln, name, default, tp, t])
        options[name]=len(output)-1
    return output, options

class Template:
    def __init__(self, fname=None):
        if fname != None:
            lines, options = parseCfgLines(open(fname).readlines())
        else:
            lines = []
            options = {}
        self.lines = lines
        self.optionIdx = options
        self.optionVals = {}
        self.results = {}

    def copy(self):
        t = Template()
        t.lines = self.lines[:]
        t.optionIdx = self.optionIdx.copy()
        t.optionVals = self.optionVals.copy()
        return t

    def output(self, f, resultMode=False):
        for ln in self.lines:
            if ln[0] in ("SPACE", "COMMENT", "???"):
                f.write(ln[1])
                f.write("\n")
                continue
            assert ln[0] == "OPTION"
            _, orig, name, default, tp, t = ln
            if ((name not in self.optionVals) or
                (self.optionVals[name] == default)):
                f.write(orig)
                f.write("\n")
            else:
                f.write("%40s = %8s # %s {!!}\n"%(name, self.optionVals[name], tp))
            if resultMode and name in self.results:
                for val, diff in self.results[name]:
                    f.write(("## % 16s: %6s\n" %(val, diff)))

    def __setitem__(self, k, v):
        self.optionVals[k] = v

    def examineOptions(self, inputFiles):
        result = {}
        N = len(self.optionIdx)
        idx = 0
        for optName in self.optionIdx.keys():
            idx += 1
            ln = self.lines[self.optionIdx[optName]]
            o, orig, name, default, tp, t = ln
            assert o == "OPTION"
            assert name == optName
            vs = t.getValues()
            if vs == None:
                continue
            sys.stdout.write("[%3d/%3d] %s"%(idx,N,optName))
            res = findOptionSettings(self, inputFiles, optName, vs)
            sys.stdout.write("\n")
            result[optName] = res
        self.results.update(result)

def runUncrustify(template, inputFiles):
    cfg = tempfile.NamedTemporaryFile('w', suffix='.cfg', prefix="tmp_encrust")
    template.output(cfg)
    cfg.flush()
    res = []
    for inpFname in inputFiles:
        inData = open(inpFname).readlines()
        p = subprocess.Popen(["uncrustify", '-c', cfg.name, '-f', inpFname ],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        outData = p.stdout.readlines()
        p.wait()
        sm = difflib.SequenceMatcher(lambda x: x.isspace(),
                                     inData, outData)
        difference = (1.0 - sm.ratio()) * (len(inData) + len(outData))
        res.append(int(difference+.4))
        sys.stdout.write(".")
        sys.stdout.flush()
    cfg.close()
    return res

def findOptionSettings(template, inputFiles, optionName, optionValues):
    t = template.copy()
    result = []
    for v in optionValues:
        t[optionName] = v
        res = sum(runUncrustify(t, inputFiles))
        result.append((v, res))
    return result

if __name__ == '__main__':
    import sys
    tmpl = Template('defaults.cfg')
    tmpl.examineOptions(sys.argv[1:])
    f = open("result.cfg",'w')
    tmpl.output(f, resultMode=True)
    f.close()
