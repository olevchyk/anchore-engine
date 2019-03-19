#!/usr/bin/env python3

import base64
import sys
import os
import re
import json
import tarfile

import anchore_engine.analyzers.utils

analyzer_name = "secret_search"

try:
    config = anchore_engine.analyzers.utils.init_analyzer_cmdline(sys.argv, analyzer_name)
except Exception as err:
    print(str(err))
    sys.exit(1)

imgname = config['imgid']
imageId = config['imgid_full']
outputdir = config['dirs']['outputdir']
unpackdir = config['dirs']['unpackdir']
rootfsdir = '/'.join([unpackdir, 'rootfs'])

matchparams = list()
regexps = list()
if 'analyzer_config' in config and config['analyzer_config']:
    if 'regexp_match' in config['analyzer_config']  and type(config['analyzer_config']['regexp_match']) == list:
        regexps = config['analyzer_config']['regexp_match']
    if 'match_params' in config['analyzer_config']  and type(config['analyzer_config']['match_params']) == list:
        matchparams = config['analyzer_config']['match_params']

if len(regexps) <= 0:
    print("No regexp configuration found in analyzer_config.yaml for analyzer '"+analyzer_name+", skipping")
    sys.exit(0)

params = {'maxfilesize':False}
if matchparams:
    for param in matchparams:
        try:
            (key, value) = param.split("=")
            if key == 'MAXFILESIZE':
                params['maxfilesize'] = int(value)

        except:
            print("WARN: could not parse parameter (should be 'key=value'), ignoring: " + str(param))

outputdata = {}
allfiles = {}
if os.path.exists(unpackdir + "/anchore_allfiles.json"):
    with open(unpackdir + "/anchore_allfiles.json", 'r') as FH:
        allfiles = json.loads(FH.read())
else:
    #fmap, allfiles = anchore_engine.analyzers.utils.get_files_from_path(unpackdir + "/rootfs")
    fmap, allfiles = anchore_engine.analyzers.utils.get_files_from_squashtar(os.path.join(unpackdir, "squashed.tar"), inpath=os.path.join(unpackdir, "rootfs"))
    with open(unpackdir + "/anchore_allfiles.json", 'w') as OFH:
        OFH.write(json.dumps(allfiles))

results = {}
with tarfile.open(os.path.join(unpackdir, "squashed.tar"), mode='r', format=tarfile.PAX_FORMAT) as tfl:
    alltnames = tfl.getnames()
    alltfiles = {}
    for name in alltnames:
        alltfiles[name] = True

    for member in tfl.getmembers():
        name = "/{}".format(member.name)
        if member.islnk() or member.issym():
            emember = anchore_engine.analyzers.utils._get_extractable_member(tfl, member, deref_symlink=True, alltfiles=alltfiles)
            if emember:
                member = emember

        if member.isreg():
            dochecks = True
            if params['maxfilesize'] and int(member.size) > params['maxfilesize']:
                dochecks = False

            if dochecks:
                with tfl.extractfile(member) as FH:
                    lineno = 0
                    for line in FH.readlines():
                        for regexp in regexps:
                            try:
                                regexpname, theregexp = regexp.split("=", 1)
                            except:
                                theregexp = regexp

                            try:
                                patt = re.match(theregexp.encode('utf-8'), line)
                                if patt:
                                    b64regexp = str(base64.encodebytes(regexp.encode('utf-8')), 'utf-8')
                                    if name not in results:
                                        results[name] = {}
                                    if b64regexp not in results[name]:
                                        results[name][b64regexp] = list()
                                    results[name][b64regexp].append(lineno)
                            except Exception as err:
                                import traceback
                                traceback.print_exc()
                                print("ERROR: configured regexp not valid or regexp cannot be applied - exception: " + str(err))
                                sys.exit(1)
                        lineno += 1
            else:
                # skipping this file because maxfilesize is set and file is larger
                pass

for name in list(results.keys()):
    buf = json.dumps(results[name])
    outputdata[name] = buf

if outputdata:
    ofile = os.path.join(outputdir, 'regexp_matches.all')
    anchore_engine.analyzers.utils.write_kvfile_fromdict(ofile, outputdata)

sys.exit(0)
