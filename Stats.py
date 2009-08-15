#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# Stats.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

from threading import Thread,Lock

class Stats(Thread):
    """ A thread-safe stats gatherer with fine-grained locks """
    def __init__(self):
        self.hitlock = Lock()
        self.postlock = Lock()
        self.jumplock = Lock()
        self.warplock = Lock()
        self.docklock = Lock()
        self.undocklock = Lock()
        self.cached_getlock = Lock()
        self.lock_list = [self.hitlock, self.postlock, self.jumplock, self.warplock, self.docklock, self.undocklock, self.cached_getlock]
        self.reset()
        Thread.__init__(self)
    def warp(self):
        self.warplock.acquire()
        self.warps += 1
        self.warplock.release()
    def dock(self):
        self.docklock.acquire()
        self.docks += 1
        self.docklock.release()
    def undock(self):
        self.undocklock.acquire()
        self.undocks += 1
        self.undocklock.release()
    def cached_get(self):
        self.cached_getlock.acquire()
        self.cached_gets += 1
        self.cached_getlock.release()
    def hit(self):
        self.hitlock.acquire()
        self.hits += 1
        self.hitlock.release()
    def post(self):
        self.postlock.acquire()
        self.posts += 1
        self.postlock.release()
    def jump(self):
        self.jumplock.acquire()
        self.jumps += 1
        self.jumplock.release()
    def lock_all(self):
        for lock in self.lock_list:
            lock.acquire()
    def unlock_all(self):
        for lock in reversed(self.lock_list):
            lock.release()
    def reset(self):
        self.lock_all()
        self.hits = 0
        self.posts = 0
        self.warps = 0
        self.jumps = 0
        self.docks = 0
        self.undocks = 0
        self.cached_gets = 0
        self.unlock_all()

#
