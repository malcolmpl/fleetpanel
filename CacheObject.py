#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# CacheObject.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

class CacheObject:
    """ class representing cached corporation information from Eve API """
    def __init__(self):
        self.data = {}
    def has(self, corpName):
        return self.data.has_key(corpName)
    def set(self, corpName, newdata, expirationTime):
        self.data[corpName] = (newdata, expirationTime)
    def expired(self, corpName):
        return True # FIXME TODO

