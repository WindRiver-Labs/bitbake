#
# Multipile Log Tail for real time logging
#
# Copyright (C) 2012 Wind River Systems, Inc.
#
# Authored by Jason Wessel <jason.wessel@windriver.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import re
import time
import sys

class LogTail(object):
    """Tail a single log file"""

    def __init__(self):
        self.file = None
        self.offset = 0
        self.filterLines = True
        self.limit = 8192
        self.cnt = 0
        self.storedLine = ""

    def openLog(self, filename, filterLines=True, limit=8192):
        try:
            self.file = open(filename, 'rb')
            self.limit = limit
            self.filterLines = filterLines
        except:
            return False
        return True

    def getLeftLine(self):
        (left, right) = self.storedLine.split('\r',1)
        self.storedLine = right
        self.cnt = len(right)
        return left

    def getLine(self):
        if self.cnt > 0 and '\r' in self.storedLine:
            return self.getLeftLine()
        while 1:
            self.offset = self.file.tell()
            line = self.file.readline()
            if line:
                if self.filterLines:
                    line = line.replace('\r\n','\r');
                    line = line.replace('\n','\r');
                    self.storedLine += line
                    self.cnt = len(self.storedLine)
                    if (self.cnt > self.limit):
                        if not '\r' in self.storedLine:
                            self.storedLine += '\r'
                        return self.getLeftLine()
                    if '\r' in self.storedLine:
                        return self.getLeftLine()
                    continue
                else:
                    return line
            self.file.seek(self.offset)
            return None

    def closeLog(self):
        if self.file:
            self.file.close()
            self.file = None

    def __del__(self):
        self.closeLog()

class MultiLogTail(object):
    """Tail mulitple log files"""

    def __init__(self, printPid=True):
        self.filelist = []
        self.trackPid = []
        self.printPid = printPid

    def openLog(self, filename, pid=0, limit=8192):
        logtail = LogTail()
        if logtail.openLog(filename, True, limit):
            self.filelist.append((logtail, filename, pid))
        else:
            if pid > 0:
                self.trackPid.append(pid)

    def displayLogs(self):
        for (logtail, filename, pid) in self.filelist:
            while 1:
                output = logtail.getLine()
                if output == None:
                    break
                if self.printPid:
                    print " " + str(pid) + ":" + output
                else:
                    print output

    def closeLogs(self):
        while 1:
            try:
                (logtail, filename, pid) = self.filelist.pop()
                logtail.closeLog()
            except:
                break

    def closeLog(self, rm_filename):
        for (logtail, filename, pid) in self.filelist:
            if filename == rm_filename:
                self.filelist.remove((logtail, filename, pid))
                logtail.closeLog()
                return
        raise Exception("File %s not in the list" % rm_filename)

    def closeLogPid(self, rm_pid):
        for (logtail, filename, pid) in self.filelist:
            if pid == rm_pid:
                self.filelist.remove((logtail, filename, pid))
                logtail.closeLog()
                return
        if rm_pid in self.trackPid:
            self.trackPid.remove(rm_pid)
            return
        print "ERROR: PID %s not in the list" % rm_pid
