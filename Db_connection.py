#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# Db_connection.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

import MySQLdb

class Db_connection:
    def __init__(self):
        self.db = MySQLdb.connection(host="127.0.0.1", user="db_username", passwd="db_password", db="db_database_name")

    def query(self, myquery):
        self.db.query( myquery )
        r = self.db.store_result()
        return r

    def get_jumps(self, li_systems):
        query_base = "SELECT mss.solarSystemName,mss2.solarSystemName FROM mapSolarSystemJumps AS mssj JOIN mapSolarSystems AS mss ON (mss.solarSystemID=fromSolarSystemID) JOIN mapSolarSystems AS mss2 ON (mssj.toSolarSystemID=mss2.solarSystemID)"
        if li_systems=="*":
            my_query = query_base + ";"
        else:
            set_systems = set(li_systems)
            my_systems = ", ".join( map( lambda x: '"' + x + '"', set_systems) )
            my_query = query_base + " WHERE mss.solarSystemName IN (%s);" % my_systems
        db_result = self.query( my_query )
        for row in db_result.fetch_row(0):
            yield row[0], row[1]

    def get_region_id_sysname(self, li_systems):
        query_base = "SELECT mr.regionName,mss.solarSystemID,mss.solarSystemName FROM mapSolarSystems AS mss JOIN mapRegions AS mr ON (mss.regionID=mr.regionID)"
        if li_systems=="*":
            my_query = query_base + ";"
        else:
            my_systems = ", ".join( map( lambda x: '"' + x + '"', li_systems ) )
            my_query = query_base + " WHERE mss.solarSystemName IN (%s);" % my_systems
        self.db.query( my_query )
        r = self.db.store_result()
        for region, id, system in r.fetch_row(0):
            yield region, id, system

    def close(self):
        self.db.close()
#
