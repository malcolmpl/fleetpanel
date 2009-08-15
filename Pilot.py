#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# Pilot.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

import pickle

class Pilot:
    def __init__(self, nick):
        self.nick = nick
        self.serverData = PilotServerData()
        self.customData = PilotCustomData(nick)

class PilotCustomData:
    properties = ["mining", "pvp", "align", "tackling", "overview", "bookmark", "skaner"]
    def __init__(self, nick):
        self.data = {}
        self.nick = nick
        for i in self.properties:
            self.data[i] = False
        self.deleted = False
        self.comment = "just joined"
        self.save()

    def load(self):
        success, pilotsdata = unpickle("PilotCustomData/" + self.nick + '.pkl')
        if success:
            self.pilotsdata = pilotsdata
        
    def save(self):
        output = open("PilotCustomData/" + self.nick + '.pkl', 'wb')
        pickle.dump(self, output)
        output.close()

class PilotServerData:
    def __init__(self):
        self.data = {}

#

