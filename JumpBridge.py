#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# JumpBridge.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

class JumpBridge:
    """ class representing a Jump Bridge between two systems. The order of from/to is irrelevant """
    def __init__(self, sys_from, planet_from, moon_from, sys_to, planet_to, moon_to, owner, password, comment=""):
        self.sys_from = sys_from
        self.planet_from = planet_from
        self.moon_from = moon_from
        self.sys_to = sys_to
        self.planet_to = planet_to
        self.moon_to = moon_to
        self.owner = owner
        self.password = password
        self.comment = comment

    def exact_to(self):
        return self.planet_to + "-" + self.moon_to

    def exact_from(self):
        return self.planet_from + "-" + self.moon_from

    def __contains__(self, item):
        return self.sys_from==item or self.sys_to==item
        
    def other_side_than(self, sys):
        if self.sys_from==sys:
            return self.sys_to
        else:
            return self.sys_from

#

