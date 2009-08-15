#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# Player.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.


class Player:
    """ class representing an Eve player current properties """
    def __init__(self, charid, charname):
        self.name = charname
        self.ID = charid
        self.cyno = False
        self.dd = 9
        self.cloak = False
        self.can_scout = False
        self.range = 0
        self.rr = False

