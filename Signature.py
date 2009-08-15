#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:
import time
from datetime import datetime

class Signature:
    def __init__(self, solar, signature, planet, typee, name, comment, creator, creation_time ):
        self.solar = solar
        self.signature = signature
        self.planet = planet
        self.typee = typee
        self.name = name
        self.comment = comment
        self.creation_time = creation_time
        self.creator = creator

