from __future__ import print_function

import os
import re

from sys import platform
from configtool.data import (
    defineValueFormat,
    defineBoolFormat,
    reHelpTextStart,
    reHelpTextEnd,
    reDefine,
    reDefineBL,
    reDefQS,
    reDefQSm,
    reDefQSm2,
    reDefBool,
    reDefBoolBL,
    reHomingOpts,
    reStartHoming,
    reEndHoming,
    reDefHoming,
    reHoming4,
)


class Printer:
    def __init__(self, settings):
        self.configFile = None

        self.cfgValues = {}
        self.settings = settings
        self.cfgDir = os.path.join(self.settings.folder, "configtool")

    def getValues(self):
        vars = [(x, self.cfgValues[x]) for x in self.cfgValues]
        return dict(vars)

    def hasData(self):
        return self.configFile != None

    def getFileName(self):
        return self.configFile

    def loadConfigFile(self, fn):
        cfgFn = os.path.join(self.cfgDir, "printer.generic.h")
        try:
            self.cfgBuffer = list(open(cfgFn))
        except:
            return False, cfgFn

        try:
            self.userBuffer = list(open(fn))
        except:
            return False, fn

        self.configFile = fn

        gatheringHelpText = False
        helpTextString = ""
        helpKey = None

        self.cfgValues = {}
        self.cfgNames = []
        self.helpText = {}

        prevLines = ""
        for ln in self.cfgBuffer:
            if gatheringHelpText:
                if reHelpTextEnd.match(ln):
                    gatheringHelpText = False
                    helpTextString = helpTextString.strip()
                    # Keep paragraphs with double-newline.
                    helpTextString = helpTextString.replace("\n\n  ", "\n\n")
                    # Keep indented lines, typically a list.
                    helpTextString = helpTextString.replace("\n\n  ", "\n\n    ")
                    helpTextString = helpTextString.replace("\n    ", "\n\n    ")
                    # Remove all other newlines and indents.
                    helpTextString = helpTextString.replace("\n  ", " ")
                    hk = helpKey.split()
                    for k in hk:
                        self.helpText[k] = helpTextString
                    helpTextString = ""
                    helpKey = None
                    continue
                else:
                    helpTextString += ln
                    continue

            m = reHelpTextStart.match(ln)
            if m:
                t = m.groups()
                gatheringHelpText = True
                helpKey = t[0]
                continue

            if ln.rstrip().endswith("\\"):
                prevLines += ln.rstrip()[:-1]
                continue

            if prevLines != "":
                ln = prevLines + ln
                prevLines = ""

            if self.parseCandidateValues(ln):
                continue

            if self.parseHoming(ln):
                continue

            self.parseDefineName(ln)
            self.parseDefineValue(ln)

        # Set all boolean generic configuration items to False, so items not yet
        # existing in the user configuration default to disabled.
        for k in self.cfgValues.keys():
            if isinstance(self.cfgValues[k], bool):
                self.cfgValues[k] = False

        # Read the user configuration. This usually overwrites all of the items
        # read above, but not those missing in the user configuration, e.g.
        # when reading an older config.
        gatheringHelpText = False
        prevLines = ""
        for ln in self.userBuffer:
            if gatheringHelpText:
                if reHelpTextEnd.match(ln):
                    gatheringHelpText = False
                continue

            if reHelpTextStart.match(ln):
                gatheringHelpText = True
                continue

            if ln.rstrip().endswith("\\"):
                prevLines += ln.rstrip()[:-1]
                continue

            if prevLines != "":
                ln = prevLines + ln
                prevLines = ""

            if self.parseCandidateValues(ln):
                continue

            if self.parseHoming(ln):
                continue

            self.parseDefineValue(ln)

        # Parsing done. All parsed stuff is now in these array and dicts.
        if self.settings.verbose >= 2:
            print(self.cfgValues)  # #defines with a value.
            print(self.cfgNames)  # Names found in the generic file.
        if self.settings.verbose >= 3:
            print(self.helpText)

        return True, None

    def parseDefineName(self, ln):
        m = reDefBool.search(ln)
        if m:
            t = m.groups()
            if len(t) == 1:
                self.cfgNames.append(t[0])
            return True

        return False

    def parseCandidateValues(self, ln):
        m = reHomingOpts.match(ln)
        if m:
            t = m.groups()
            if len(t) == 1:
                if "HOMING_OPTS" in self.cfgValues:
                    if t[0] not in self.cfgValues["HOMING_OPTS"]:
                        self.cfgValues["HOMING_OPTS"].append(t[0])
                else:
                    self.cfgValues["HOMING_OPTS"] = [t[0]]
            return True

    def parseHoming(self, ln):
        m = reDefHoming.search(ln)
        if m:
            t = m.groups()
            if len(t) == 1:
                n = reHoming4.search(t[0])
                if n:
                    u = n.groups()
                    if len(u) == 4:
                        t2 = []
                        for x in u:
                            t2.append(x)

                        self.cfgValues["HOMING_STEP1"] = t2[0]
                        self.cfgValues["HOMING_STEP2"] = t2[1]
                        self.cfgValues["HOMING_STEP3"] = t2[2]
                        self.cfgValues["HOMING_STEP4"] = t2[3]

                        return True
                return None
            return True

    def parseDefineValue(self, ln):
        m = reDefQS.search(ln)
        if m:
            t = m.groups()
            if len(t) == 2:
                m = reDefQSm.search(ln)
                if m:
                    t = m.groups()
                    tt = re.findall(reDefQSm2, t[1])
                    if len(tt) == 1 and (t[0] in self.cfgNames):
                        self.cfgValues[t[0]] = tt[0], True
                        return True
                    elif len(tt) > 1 and (t[0] in self.cfgNames):
                        self.cfgValues[t[0]] = tt, True
                        return True

        m = reDefine.search(ln)
        if m:
            t = m.groups()
            if len(t) == 2 and (t[0] in self.cfgNames):
                if reDefineBL.search(ln):
                    self.cfgValues[t[0]] = t[1], True
                else:
                    self.cfgValues[t[0]] = t[1], False
                return True

        m = reDefBool.search(ln)
        if m:
            t = m.groups()
            # Accept booleans, but not those for which a value exists already.
            # Booleans already existing as values are most likely misconfigured
            # manual edits (or result of a bug).
            if (
                len(t) == 1
                and t[0] in self.cfgNames
                and not (
                    t[0] in self.cfgValues and isinstance(self.cfgValues[t[0]], tuple)
                )
            ):
                if reDefBoolBL.search(ln):
                    self.cfgValues[t[0]] = True
                else:
                    self.cfgValues[t[0]] = False
                return True

        return False

    def saveConfigFile(self, path, values):
        if not values:
            values = self.cfgValues

        if self.settings.verbose >= 1:
            print("Saving printer: %s." % path)
        if self.settings.verbose >= 2:
            print(values)

        fp = file(path, "w")
        self.configFile = path

        skipToHomingEnd = False

        for ln in self.cfgBuffer:
            m = reStartHoming.match(ln)
            if m:
                fp.write(ln)
                sstr = "%s, %s, %s, %s" % (
                    (values["HOMING_STEP1"]),
                    (values["HOMING_STEP2"]),
                    (values["HOMING_STEP3"]),
                    (values["HOMING_STEP4"]),
                )
                fp.write("DEFINE_HOMING(%s)\n" % sstr)
                skipToHomingEnd = True
                continue

            if skipToHomingEnd:
                m = reEndHoming.match(ln)
                if m:
                    fp.write(ln)
                    skipToHomingEnd = False
                continue

            m = reDefine.match(ln)
            if m:
                t = m.groups()
                if len(t) == 2 and t[0] in values.keys():
                    v = values[t[0]]
                    self.cfgValues[t[0]] = v
                    if v[1] == False:
                        fp.write("//")
                    fp.write(defineValueFormat % (t[0], v[0]))
                else:
                    if t[0] == "CANNED_CYCLE":
                        # Known to be absent in the GUI. Worse, this value is replaced
                        # by the one in the metadata file.
                        #
                        # TODO: make value reading above recognize wether this value is
                        #       commented out or not. Reading the value its self works
                        #       already. Hint: it's the rule using reDefQS, reDefQSm, etc.
                        #
                        # TODO: add a multiline text field in the GUI to deal with this.
                        #
                        # TODO: write this value out properly. In /* comments */, if
                        #       disabled.
                        #
                        # TODO: currently, the lines beyond the ones with the #define are
                        #       treated like arbitrary comments. Having the former TODOs
                        #       done, this will lead to duplicates.
                        fp.write(ln)
                    else:
                        print("Value key " + t[0] + " not found in GUI.")

                continue

            m = reDefBoolBL.match(ln)
            if m:
                t = m.groups()
                if len(t) == 1 and t[0] in values.keys():
                    v = values[t[0]]
                    self.cfgValues[t[0]] = v
                    if v == "" or v == False:
                        fp.write("//")
                    fp.write(defineBoolFormat % t[0])
                else:
                    print("Boolean key " + t[0] + " not found in GUI.")

                continue

            fp.write(ln)

        fp.close()

        return True
