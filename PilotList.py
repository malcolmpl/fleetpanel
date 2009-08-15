#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# PilotList.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

from Pilot import Pilot
class PilotList:
    """ class representing a set of Pilot objects """
    def __init__(self):
        self.data = {}
        
    def getPilot(self, nick):
        if not self.data.has_key(nick):
            self.data[nick] = Pilot(nick)
        return self.data[nick]

    def has_key(self, key):
        if self.data.has_key(key):
            return True
        return False

#

