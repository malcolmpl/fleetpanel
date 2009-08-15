#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# FleetPanel.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

print "start of imports"
import BaseHTTPServer
from BaseHTTPServer import HTTPServer
import cgi, random, sys
import httplib, urllib # for api
import sys
import pickle
import time
import os
from datetime import datetime, timedelta, date
from threading import Lock
from SocketServer import ThreadingMixIn
from string import capwords
import threading
import string
import copy
import Drawing
from Signature import Signature
from JumpBridge import JumpBridge
from Db_connection import Db_connection
from Roman import Roman
from Player import Player
from PilotList import PilotList
from CacheObject import CacheObject
from Stats import Stats
print "end of imports"

global g_allowed_alliance_ids
g_allowed_alliance_ids = ["-1"] # YOU MUST FILL THIS
global g_allowed_corp_ids
g_allowed_corp_ids = ["-1"] # YOU MUST FILL THIS

global global_refresh_rate
global_refresh_rate = 600 # how often should the panel autorefresh (apart from refresh after jump/undock etc)

global g_home_system
g_home_system = "Jita"

global g_password
g_password = {}
g_password[1] = "password1" # normal usage if the panel is restricted
g_password[2] = "password2" # fleet commanders
g_password[3] = "password3" # superadmin

global g_force_draw_jump_bridges
g_force_draw_jump_bridges = True

global g_print_headers_when_alliance_invalid
g_print_headers_when_alliance_invalid = True

###### NO NEED TO EDIT BELOW THIS LINE (apart from corporation api stuff) ######

def getMemberDataCache(charid, userid, apikey, corpname, cacheObject):
    if not cacheObject.has(corpname) or cacheObject.expired(corpname):
        newdata, expirationTime = getMemberData(charid, userid, apikey, corpname)
        cacheObject.set(corpname, newdata, expirationTime)
        return newdata
    else:
        return cacheObject.get(corpname)

def getMemberData(charid, userid, apikey, corpname):
    # based on the Eve online api example
    params = urllib.urlencode( {
        'characterID': charid,
        'userid': userid,
        'apikey': apikey,
    } )
    headers = { "Content-type": "application/x-www-form-urlencoded" }
    conn = httplib.HTTPConnection("api.eve-online.com")
    conn.request("POST", "/corp/MemberTracking.csv.aspx", params, headers)
    
    response = conn.getresponse()
    
    rawdata = response.read()
    
    dump = open("getMemberDataRaw/" + str( int( time.time() ) ), "w")
    dump.write(rawdata)
    dump.close()
    
    pilotlist = []
    for row in rawdata.split('\n'):
        rowlist = row.split(',') # character,start date,last logon,last logoff,base,location,ship,title,roles,grantable roles
        if len(rowlist)<7: # newline on the very end
            continue
        nick = rowlist[0]
        if nick=="" or nick=="character":
            continue
        pilotDict = {}
        pilotDict['nick'] = rowlist[0]
        pilotDict['startdate'] = rowlist[1]
        pilotDict['lastlogon'] = rowlist[2]
        pilotDict['lastlogoff'] = rowlist[3]
        pilotDict['base'] = rowlist[4]
        pilotDict['location'] = rowlist[5]
        pilotDict['ship'] = rowlist[6]
        pilotDict['title'] = rowlist[7]
        pilotDict['roles'] = rowlist[8]
        pilotDict['grantableroles'] = rowlist[9].strip()
        pilotDict['corpname'] = corpname
        pilotlist.append(pilotDict)

    # FIXME: api cache must be implemented
    #cachedUntil = time.time()
    conn.request("POST", "/corp/MemberTracking.xml.aspx", params, headers)
    response = conn.getresponse()
    cachedUntil = response.read().split('\n')[-2].split('>')[1].split('<')[0]
    #print "CACHED UNTIL:", cachedUntil
    conn.close()
    return pilotlist, cachedUntil

def unpickle(filename):
    success = False
    try:
        pkl_file = open(filename, 'rb')
        data = pickle.load(pkl_file)
        pkl_file.close()
        success = True
    except:
        # file missing?
        data = None
    #finally:
    #    pkl_file.close()
    return success, data

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    allow_reuse_address = True
    daemon_threads = True

# ///////////////////////////////////////  GENERAL  \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    CACHED = 2
    li_shiptypes_ordered = [ "Unknown", "TITAN", "Mothership", "DREAD", "CAPS", "Black Ops", "Marauder", "BS", "Command", "BC", "HAC", "HIC", "Recon", "Logistic", "Cruiser", "DICTOR", "Destroyer", "Covert", "CEP", "Frigate", "NOOBSHIP", "Capital Industrial Ship", "Jump Freighter", "Freighter", "Transport", "Industrial", "Electronic Attack", "Assault", "Mining Barge", "Exhumer", "Shuttle", "EGG" ]

    def do_GET(self):
        self.decide_panel("GET")

    def do_POST(self):
        self.decide_panel("POST")

    def decide_panel(self, method):
        if self.path=="/favicon.ico":
            self.send_response(404)
            return
        if not self.headers.has_key('Host'):
            return
        self.host = self.headers['Host']
        self.generate_start_time = time.time()
        self.out_init()
        global allow_global_refresh_rate_change
        # TODO: get_password()
        self.password = ""
        q_mark = self.path.find("?")
        self.refresh_path = self.path
        if q_mark != -1:
            self.password = self.path[q_mark+1:]
            self.path = self.path[:q_mark]

        self.clearance = self.security_clearance()
        image = False
        if not self.headers.has_key('Eve.trusted') or self.headers['Eve.trusted']=="no":
            self.handle_untrusted()

        elif allow_global_refresh_rate_change and self.path.startswith("/set_global_refresh_rate/"):
            self.handle_global_refresh_rate_change()

        elif self.path=="/img/map.png":
            if not self.security_query("map_image_data"):
                self.send_response(403)
                return
            self.handle_map()
            image = True
        elif self.path=="/img/stats.png":
            if not self.security_query("stats_image_data"):
                self.send_response(403)
                return
            self.handle_stats()
            image = True
        else: # war panel
            self.handle_war_panel(method)
        if not image:
            self.makefooter()
        self.out_commit()

    def send_headers_html(self):
        self.send_headers_by_type("text/html")

    def send_headers_png(self):
        self.send_headers_by_type("image/png")

    def send_headers_by_type(self, content_type):
        self.send_response(200)
        self.send_header("Pragma", "no-cache")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-type", content_type)

    def handle_war_panel(self, method):
        self.send_headers_html()
        out = self.out
        global global_refresh_rate
        self.refresh_rate = global_refresh_rate
        global g_allowed_alliance_ids
        global g_allowed_corp_ids
        if not self.headers.has_key('Eve.trusted'):
            self.end_headers()
            self.makeheader()
            out("<br>Use Eve InGameBrowser!")
        elif method=="POST" and not self.headers.has_key('Eve.Charid'):
            self.end_headers()
            self.makeheader()
            out("<br>NOT EVE-TRUSTED! PLEASE ADD THIS SITE TO TRUSTED in OPTIONS/TRUSTED SITES!")
            #for h in self.headers:
            #    out("<br>" + h + ": " + self.headers[h])
        #elif not self.headers.has_key('eve.allianceid') or self.headers['eve.allianceid'] not in g_allowed_alliance_ids: # not our alliance?
        elif not self.headers.has_key('eve.corpid') or self.headers['eve.corpid'] not in g_allowed_corp_ids: # TODO: FIXME: HACK
            self.end_headers()
            self.makeheader()
            global g_print_headers_when_alliance_invalid
            if g_print_headers_when_alliance_invalid:
                for h in self.headers:
                    out("<br>" + h + ": " + self.headers[h])
            else:
                out("connection refused") # this should confuse unauthorized players (it's by design)
        elif self.headers['Eve.Stationname'] == "None" and self.headers['Eve.Nearestlocation'] == "None":
            dur_refresh_delay = 3
            self.send_header("refresh", "%s;URL=%s" % (dur_refresh_delay, self.refresh_path) )
            self.end_headers()
            self.makeheader()
            out("Wait %ss, refreshing..." % dur_refresh_delay)
        else:
            global g_stats
            g_stats.hit()
            self.war_panel(method)

    def handle_stats(self):
        self.send_headers_png()
        self.end_headers()
        self.conditional_output(False, False, "stats_image_data", Drawing.Draw.gnuplot_return, 30)

    def handle_map(self):
        self.send_headers_png()
        self.end_headers()
        global jump_bridges
        forced_systems = set()
        global g_force_draw_jump_bridges
        if g_force_draw_jump_bridges:
            for jb in jump_bridges:
                forced_systems.add( jb.sys_from )
                forced_systems.add( jb.sys_to )
        highlighted_systems = set()
        global g_home_system
        if g_home_system!="":
            highlighted_systems.add( g_home_system )
        self.conditional_output(False, False, "map_image_data", Drawing.Draw.graphviz_return, warPlayerList, self.get_player_filters("default"), jump_bridges, forced_systems, highlighted_systems )

    def handle_untrusted(self):
        self.send_headers_html()
        self.send_header("eve.trustme", "http://" + self.host + "/::PRESS YES OR THIS WILL NOT WORK!")

    def handle_global_refresh_rate_change(self):
        self.send_headers_html()
        self.end_headers()
        splited = self.path.split("/")
        global global_refresh_rate
        global_refresh_rate = int( splited[2] )

    def link(self, addr, comment):
        if self.password!="":
            return "<A HREF=\"%s?%s\">%s</A>" % (addr, self.password, comment)
        else:
            return "<A HREF=\"%s\">%s</A>" % (addr, comment)

# \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\  GENERAL  /////////////////////////////////////

# /////////////////////////////////////// UTILITIES \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def getFormDict(self):
        form = cgi.FieldStorage(
            fp = self.rfile, 
            headers = self.headers,
            environ = {'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     }
        )
        formdict = {}
        for field in form.keys():
            field_item = form[field]
            if field_item.filename:
                continue
            else:
                formdict[field] = form[field].value
                #out('<br>\t%s=%s\n' % (field, form[field].value))
        #cgi.escape(urllib.unquote(ship)) # doesn't seem nessecary
        return formdict

    def td(self, text, args=""):
        output = ""
        if args!="":
            output += "  <TD %s>" % args
        else:
            output += "  <TD>"
        output += text
        output += "  </TD>"
        return output

    def tr(self, li_td, args=""):
        output = ""
        if args!="":
            output += "  <TR %s>" % args
        else:
            output += "  <TR>"
        output += "".join( li_td )
        output += "  </TR>"
        return output

    def red_text(cls, text):
        return "<FONT SIZE=7 COLOR=\"FF0000\">" + text + "</FONT>"

    def makeheader(self):
        out = self.out
        out("<HTML><HEAD>")
        title = "Fleet Panel"
        out("<TITLE>%s</TITLE>" % title)
        out("<META HTTP-EQUIV=\"Pragma\" CONTENT=\"no-cache\">")
        out("<META HTTP-EQUIV=\"Expires\" CONTENT=\"-1\">")
        out("</HEAD><BODY>")

    def makefooter(self):
        out = self.out
        out("<BR><FONT SIZE=2>")
        out("generate time: " + str(int((time.time() - self.generate_start_time)*1000)) + "ms")
        if self.lag_compensation>=1:
            out(", %ss lag-compensated" % self.lag_compensation)
        out("</FONT>")
        out("</BODY>")
        out("</HTML>")

    def out_init(self):
        self.lag_compensation = 0
        self.out_buffer = []

    def out(self, arg):
        self.out_buffer.append(arg)

    def out_commit(self):
        output = "".join(self.out_buffer)
        modifier = 0
        if output.startswith("\r\n"):
            modifier = -2
        self.send_header("Content-Length", "%s" % (len(output)+modifier,) )
        self.wfile.write(output)

    def end_headers(self): # NOTE: overload!
        if self.__dict__.has_key("out_buffer"):
            self.out_buffer.insert(0, "\r\n")
        else:
            self.wfile.write("\r\n")

    def getSecurityPolicy(self):
        global security_policy
        return security_policy

    def cache_or_true(self, security_type):
        global lockable_items
        if security_type in lockable_items:
            return self.CACHED
        else:
            return True

    def common_policy(self, policy, clearance, sec_type):
        if policy==0:
            if clearance>=2:
                return True
            return self.cache_or_true(sec_type)
        elif policy==1:
            if clearance>=2:
                return True
            return self.cache_or_true(sec_type)
        elif policy==2 and clearance>=2:
            return True
        else:
            return False

    def security_query(self, sec_type):
        # TODO: refactor
        policy = self.getSecurityPolicy()
        clearance = self.clearance
        if sec_type=="war_summary":
            return self.common_policy(policy, clearance, sec_type)
        elif sec_type in map(lambda item: "top_summary_" + item, ["cloak", "cyno", "can_scout", "losses"]):
            return self.common_policy(policy, clearance, sec_type)
        elif sec_type=="sig_view":
            return self.common_policy(policy, clearance, sec_type) # FIXME HACK
        elif sec_type=="sig_set":
            return self.common_policy(policy, clearance, sec_type) # FIXME HACK
        elif sec_type=="jb_view":
            return self.common_policy(policy, clearance, sec_type) # FIXME HACK
            if clearance>=2:
                return True
        elif sec_type=="jb_set":
            return self.common_policy(policy, clearance, sec_type) # FIXME HACK
            if clearance>=3:
                return True
        elif sec_type=="losses_table":
            return self.common_policy(policy, clearance, sec_type)
        elif sec_type=="autopilot":
            return self.common_policy(policy, clearance, sec_type)
        elif sec_type=="fleet_table":
            if clearance>=2:
                return True
            elif policy==0:
                return self.cache_or_true(type)
            elif policy==1 and clearance>=1:
                return self.cache_or_true(type)
        elif sec_type=="disconnected_table":
            if clearance>=1:
                return self.cache_or_true(type)
        elif sec_type=="stats_image" or sec_type=="stats_image_data":
            if clearance>=2:
                return True
        elif sec_type=="map_image" or sec_type=="map_image_data":
            return self.common_policy(policy, clearance, sec_type) # FIXME HACK
            if clearance>=2:
                return True
        elif sec_type=="admin_list":
            if clearance>=2:
                return True
        elif sec_type=="admin_panel":
            if clearance>=2:
                return True
        elif sec_type=="password_set_1":
            if clearance>=2:
                return True
        elif sec_type=="password_set_2":
            if clearance>=3:
                return True
        elif sec_type=="fleet_invite_set":
            if clearance>=2:
                return True
        elif sec_type=="security_policy_set":
            if clearance>=2:
                return True
        return False
        
    def security_clearance(self):
        global g_password
        for i in range(1,4):
            if self.password==g_password[i]:
                return i
        return 0

    def get_compensated_refresh_rate(self, last_activity, name):
        # warrning: it was quite hart to make this work. If ever introducing unit-tests, start here.
        how_much_did_it_take = time.time() - last_activity
        global compensated_rates
        was_ordered = self.refresh_rate
        if compensated_rates.has_key(name):
            was_ordered = compensated_rates[name]

        lag = how_much_did_it_take - was_ordered
        if lag>self.refresh_rate*3:
            compensation = 0
        elif lag<=0:
            compensation = 0
        elif self.refresh_rate - lag < 15:
            compensation = self.refresh_rate - 15 # if we'll keep refreshing his browser he won't be able to setup his ship
        else:
            compensation = lag
        refresh_time = self.refresh_rate - compensation
        #print name, ":", "it took", how_much_did_it_take, "was_ordered", was_ordered, "lag", lag, "compensation", compensation, "refresh_time", refresh_time
        compensated_rates[name] = refresh_time
        return int(compensation), int(refresh_time)

# \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\ UTILITIES /////////////////////////////////////

# /////////////////////////////////////// WAR PANEL \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def war_panel(self, method):
        out = self.out

        player, old_activity = self.process_headers(warPlayerList)
        player.loggedoff = False
        
        self.clearance = self.security_clearance()
        action = self.process_form(player) # this can change clearance!
        player.clearance = self.clearance
        if self.password:
            self.refresh_path = self.path + "?" + self.password

        self.lag_compensation, refresh_time = self.get_compensated_refresh_rate(old_activity, player.name)
        self.send_header("refresh", "%s;URL=%s" % (refresh_time, self.refresh_path) )
        self.send_header("refresh", "sessionchange;URL=%s" % self.refresh_path)
        self.end_headers()
        self.makeheader()
        edit_item = None

        if action==None or action=="update":
            if self.path!="/simple":
                self.make_war_menu(warPlayerList)
                self.make_ship_form(player) ###
        elif action=="loss":
            self.make_war_menu(warPlayerList)
            self.make_ship_form(player) ###
            out("The fleet panel is deeply sorry about Your recent loss of %s in %s. <BR>" % (player.ship, player.solar) )
            out("Now, get a new ship and get back to the fight!<BR>")
            out("<BR>")
            lock_warPlayerList.acquire() ### XXX LOCK ACQUIRE XXX
            losses.insert(0, copy.copy( warPlayerList[player.name] ) ) # get old player state (he can be in clonebay by now)
            pickle.dump(losses, open("losses.pkl", "w+"))
            lock_warPlayerList.release() ### XXX LOCK RELEASE XXX
            player.ship = "Capsule"
            player.cloak = False
            player.cyno = False
        elif action=="logout":
            out("You are logged out. Close this window now!<BR>")
            player.loggedoff = True
        elif action=="jb":
            self.make_war_menu(warPlayerList)
            self.make_ship_form(player) ###
        elif action=="signature":
            self.make_war_menu(warPlayerList)
            self.make_ship_form(player) ###
        elif type(action)==tuple:
            if action[0]=="signature":
                self.make_war_menu(warPlayerList)
                self.make_ship_form(player) ###
                sig = action[1]
                ts = datetime.utcfromtimestamp( sig.creation_time )
                datestamp = txt( ts.strftime("%m%d") )
                sigdata = [ datestamp, sig.typee[:3] ]
                if len(sig.name)>1:
                    sigdata.append( txt(sig.name) )
                if len(sig.comment)>1:
                    sigdata.append( txt(sig.comment) )
                description = "&nbsp;".join( sigdata )
                location = sig.signature
                if sig.planet!="":
                    location += ", %s" % sig.planet
                out("<font color=red><B>Bookmark name:</B></font> %s&nbsp;(%s)" % (description, location ) )
                out("<BR>")
            elif action[0]=="signature-missing":
                out("<font color=red><B>signature %s was deleted by someone else, You can't edit it</B></font>" % (action[1] ) )
            elif action[0]=="signature-edit":
                edit_item = action[1]
            elif action[0]=="autopilot":
                self.make_war_menu(warPlayerList)
                self.make_ship_form(player) ###
                self.make_road_plan( action[1], action[2] )


        lock_warPlayerList.acquire() ### XXX LOCK ACQUIRE XXX
        warPlayerList[player.name] = player ###
        pickle.dump(warPlayerList, open("warPlayerList.pkl", "w+"))
        lock_warPlayerList.release() ### XXX LOCK RELEASE XXX

        if action=="logout":
            pass
        elif player.ship == "Unknown":
            out( self.red_text("NO SHIP TYPE! Please enter ship type and press UPDATE") + "<BR><BR>")
        elif time.time() - player.last_activity > 600:
            out( self.red_text("Please enter ship type and press UPDATE") + "<BR><BR>")
        elif self.path=="/simple": # lagless
            statusline = []
            for i in ("cloak", "cyno", "can_scout"):
                if player.__dict__[i]==True:
                    statusline.append("has " + i)
                else:
                    statusline.append("no " + i)
            out("You are piloting %s (%s).<BR>" % (player.ship, ", ".join(statusline)) )
            out("Click %s to setup Your ship.<BR><BR>" % self.link("/start", "here"))
            if self.security_query("war_summary"):
                self.make_war_summary(warPlayerList)
        elif self.path=="/start" or self.path=="/": # default
            if action!="update":
                out("<font size=6>Please set Your ship type in the form above.</font><BR>")
            out("<font size=7><u>Do NOT close this window</u>!</font> <BR>")
            out("<font size=6>You can resize it or minimize it.</font> <BR>")
            out("Auto-Refresh: every %ss, after jump, after dock/undock <BR>" % self.refresh_rate)
            out("If the fleetop is over or You have to go, press the LOGOUT button. <BR>")
        elif self.path.startswith('/admin'):
            self.conditional_output(True, False, "losses_table", self.make_losses_table)
            self.conditional_output(False, False, "disconnected_table", self.make_disconnected_table, warPlayerList)
            if self.security_query("admin_panel"):
                self.make_admin_form(warPlayerList, player)
            self.conditional_output(True, False, "war_summary" , self.make_war_summary, warPlayerList)
        elif self.path.startswith('/losses'):
            self.conditional_output(False, False, "disconnected_table", self.make_disconnected_table, warPlayerList)
            self.conditional_output(True, False, "losses_table", self.make_losses_table, long=True)
        elif self.path=="/map2":
            if self.security_query("map_image"):
                out( self.make_map2_img() )
        elif self.path=="/sig":
            self.make_sig_view(player, edit_item)
        elif self.path=="/jb":
            self.make_jb_view(player) #, edit_item)
        elif self.path=="/autopilot" or action=="autopilot":
            self.make_autopilot_form(player)
        elif self.path=="/map":
            self.make_map_img(player)
        elif self.path=="/locations":
            self.output_helper(warPlayerList, 1)
        elif self.path=="/systems":
            self.output_helper(warPlayerList, 2)
        elif self.path.startswith('/details'):
            self.output_helper(warPlayerList, 3)
        elif self.path=="/cyno" or self.path=="/cloak" or self.path=="/remote" or self.path=="/can_scout":
            self.output_helper(warPlayerList, 3)
        else:
            pass # menu is displayed
        return

    def make_restricted_message(self, item, linkmode=False):
        out = self.out
        text = item.replace("_"," ") + " view was restricted by the fleet commander"
        if linkmode:
            out("<A ALT=\"%s\">?</A>" % text)
        else:
            out("<FONT SIZE=4 COLOR=\"990000\">%s</FONT><BR><BR>" % text)

    def conditional_output(self, notify, linkmode, sec_type, func, *args, **args2):
        out = self.out
        mode = self.security_query(sec_type)
        global locks
        if mode==self.CACHED:
            warmed = False
            locks[sec_type].acquire() ###
            if cache_is_cold(sec_type):
                cache_fill( sec_type, func(*args, **args2) )
                warmed = True
            locks[sec_type].release() ###
            if not warmed:
                global g_stats
                g_stats.cached_get()
            out( cache_get(sec_type) )
        elif mode==True:
            locks[sec_type].acquire() ###
            cache_fill(sec_type, func(*args, **args2) )
            locks[sec_type].release() ###
            out( cache_get(sec_type) )
        elif notify:
            self.make_restricted_message(sec_type, linkmode)

    def output_helper(self, warPlayerList, mode):
        self.conditional_output(True, False, "losses_table", self.make_losses_table)
        self.conditional_output(False, False, "disconnected_table", self.make_disconnected_table, warPlayerList)
        self.conditional_output(True, False, "fleet_table", self.make_fleet_table_helper, warPlayerList, mode=3)
        self.conditional_output(True, False, "war_summary" , self.make_war_summary, warPlayerList)

    def process_headers(self, warPlayerList):
        dockmarker = " (docked)"
        charid = self.headers['Eve.Charid']
        charname = self.headers['Eve.Charname']
        if warPlayerList.has_key(charname):
            player = warPlayerList[charname]
            old_activity = player.last_activity
            old_solar = player.solar
            old_location = player.location
        else:
            player = Player(charid, charname)
            old_activity = -1
            old_solar = None
            old_location = None
        player.solar = self.headers['Eve.Solarsystemname']
        player.corpname = self.headers['Eve.Corpname']
        player.corprole = int(self.headers['Eve.Corprole'])
        player.region = self.headers['Eve.Regionname']
        player.constellation = self.headers['Eve.Constellationname']

        player.last_activity = time.time()
        player.last_ip = self.client_address[0]
        if self.headers['Eve.Stationname']!="None":
            player.location = self.headers['Eve.Stationname'] + dockmarker
        else:
            player.location = self.headers['Eve.Nearestlocation']
            if player.location.startswith("Stargate"):
                start = player.location.find('(')
                end = player.location.find(')')
                stargate_target = player.location[start+1:end]
                player.location = player.solar + " Stargate" + " -&gt; " + stargate_target
        if player.location.startswith( player.solar + ' ' ):
            player.location = player.location[len(player.solar + ' '):]
        if player.location in map(Roman.romanize, range(1,25)) or player.location[:player.location.find(' ')] in map(Roman.romanize, range(1,25)):
            player.location = "Planet " + player.location

        new_solar = player.solar
        new_location = player.location
        # handle stats
        global g_stats
        if old_solar==None or old_location==None:
            pass # a new Player object
        elif old_solar!=new_solar:
            g_stats.jump()
        elif old_location!=new_location:
            docked = False
            undocked = False
            if old_location.endswith(dockmarker):
                undocked = True
                g_stats.undock()
            if new_location.endswith(dockmarker):
                docked = True
                g_stats.dock()
            # in theory, a player could mysteriously travel between stations without a refresh in-between
            if docked:
                if new_location!=old_location + dockmarker:
                    g_stats.warp()
            elif undocked:
                if old_location!=new_location + dockmarker:
                    g_stats.warp()
            else:
                g_stats.warp()
        return player, old_activity

    def make_losses_table(self, long=False):
        global losses
        if long:
            return self.make_simple_table_helper(losses, "losses_long")
        else:
            return self.make_simple_table_helper(losses, "losses")

    def make_disconnected_table(self, di_players):
        return self.make_simple_table_helper(di_players, "disconnected")

    def make_simple_table_helper(self, di_players, mode):
        # TODO: this one is a mess.
        #  di_players is a list if mode=losses or losses_long.
        #  Otherwise, it's a dict.
        #  Data structures were changed, but not everywhere yet
        # TODO: this one could use a refactor
        if mode=="losses_long":
            action = txt("was killed")
            filtry = self.get_player_filters("default", (0, 6*60*60) )
        elif mode=="losses":
            action = txt("was killed")
            filtry = self.get_player_filters("default", (0, 5*60) )
        elif mode=="admins":
            action = txt("is logged as admin, level")
            filtry = self.get_player_filters("admins", (0, 5*60) )
        elif mode=="disconnected":
            action = txt("disconnected")
            global global_refresh_rate
            filtry = self.get_player_filters("default", (global_refresh_rate+20, global_refresh_rate+5*60) )
        buffer = []
        spacer = False
        for item in di_players:
            if type(di_players)==dict:
                player = di_players[item]
            else:
                player = item
            if self.filterPlayer(filtry, player):
                if mode=="admins":
                    #print "admin hit", player.ID, player.name, action, player.clearance
                    buffer.append("<A HREF=\"showinfo:1377//%s\">%s</A>&nbsp;%s&nbsp;%s<BR>" % (player.ID, txt(player.name), action, txt(str(player.clearance)) ) )
                else:
                    happened_ago_s = time.time() - player.last_activity
                    ago = txt( ago_string( happened_ago_s ))
                    buffer.append( "%s&nbsp;<A HREF=\"showinfo:1377//%s\">%s</A>&nbsp;%s&nbsp;%sago<BR>" % (txt(player.ship), player.ID, txt(player.name), action, ago ) )
                spacer = True
        if spacer:
            buffer.append("<BR>")
        return "".join(buffer)
        
    def make_map_img(self, player):
        out = self.out
        out("<IMG SRC=\"http://evemaps.dotlan.net/img/%s.gif\"><BR>" % capwords(player.region).replace(' ', '_') )

    @classmethod
    def get_player_filters(cls, what, activity=(0, 90), shiptype=None):
        filtry = []
        filtry.append( lambda player: time.time() - player.last_activity >= activity[0] and time.time() - player.last_activity < activity[1] )
        filtry.append( lambda player: player.loggedoff==False )
        if what=="cyno":
            filtry.append( lambda player: player.cyno==True )
        elif what=="cloak":
            filtry.append( lambda player: player.cloak==True )
        elif what=="remote":
            filtry.append( lambda player: player.rr==True )
        elif what=="can_scout":
            filtry.append( lambda player: player.can_scout==True )
        elif what=="admins":
            filtry.append( lambda player: player.clearance>0 )
        elif what=="shiptype":
            filtry.append( lambda player: getShipClass(player.ship)==shiptype )
        elif isinstance(what, tuple):
            if what[0]=="location":
                location = what[1]
                filtry.append( lambda player: player.solar==location or player.region==location)
        if len(filtry)==0:
            filtry.append( lambda player: True )
        return filtry

    def make_fleet_table_helper(self, di_players, mode=1):
        if self.path.startswith("/cyno"):
            filtry = self.get_player_filters("cyno")
        elif self.path.startswith("/cloak"):
            filtry = self.get_player_filters("cloak")
        elif self.path.startswith("/remote"):
            filtry = self.get_player_filters("remote")
        elif self.path.startswith("/can_scout"):
            filtry = self.get_player_filters("can_scout")
        elif self.path.startswith("/details"):
            location = self.path.replace('/details/', '')
            if location!='/details':
                filtry = self.get_player_filters( ("location", location) )
            else:
                filtry = self.get_player_filters( "default" )
        else:
            filtry = self.get_player_filters( "default" )
        return self.make_fleet_table( di_players, mode, filtry )

    @classmethod
    def filterPlayer(cls, filters, player):
        for filterek2 in filters:
            if not filterek2(player):
                return False
        return True

    def purge_db(self, warPlayerList): # NOTE: this can be used if warPlayerList gets corrupted or if You change the data structure format
        pops = []
        for playername2 in warPlayerList:
            player2 = warPlayerList[playername2]
            pops.append(playername2)
        for popek in pops:
            warPlayerList.pop(popek)

    def process_form(self, player):
        # TODO: since adding an admin panel, this function needs a refactor
        ship = "Unknown"
        out = self.out
        global ship_list
        if self.headers.has_key('content-type'):
            form = self.getFormDict()
            if len(form)==0:
                pass # form = {} on first "refresh" when the player accepts the trust statement
            else:
                global g_stats
                g_stats.post()
                #print 'Form data:'
                #for f in form:
                #    print "form[" + f + "]=" + form[f]
                if form.has_key('password'):
                    self.password = cgi.escape( urllib.unquote( form['password'] ) )
                    self.clearance = self.security_clearance() # can change since the form
                if form.has_key('autopilot'):
                    if self.security_query("autopilot"):
                        sys_from = ""
                        sys_to = ""
                        if form.has_key('sys_from') and len( form['sys_from'] )>0:
                            sys_from = cgi.escape( urllib.unquote( form['sys_from'] ) )
                        if form.has_key('sys_to') and len( form['sys_to'] )>0:
                            sys_to = cgi.escape( urllib.unquote( form['sys_to'] ) )
                        return "autopilot", sys_from, sys_to
                    else:
                        out("unauthorized!")
                    return "autopilot"
                elif form.has_key('jb_set'):
                    #ble.append( ("Source system", "jb_src_sys", 32) )
                    #ble.append( ("Source planet", "jb_src_planet", 2) )
                    #ble.append( ("Source moon", "jb_src_moon", 2) )
                    #ble.append( ("Destination system", "jb_dst_sys", 32) )
                    #ble.append( ("Destination planet", "jb_dst_planet", 2) )
                    #ble.append( ("Destination moon", "jb_dst_moon", 2) )
                    #ble.append( ("Password", "jb_password", 32) )
                    #ble.append( ("Owner", "jb_owner", 16) )
                    #ble.append( ("Comment", "jb_comment", 127) )
                    sys_from = cgi.escape( urllib.unquote( form.get( "jb_src_sys", "" ) ) )
                    planet_from = cgi.escape( urllib.unquote( form.get( "jb_src_planet", "0" ) ) )
                    moon_from = cgi.escape( urllib.unquote( form.get( "src_moon", "0" ) ) )
                    sys_to = cgi.escape( urllib.unquote( form.get( "jb_dst_sys", "" ) ) )
                    planet_to = cgi.escape( urllib.unquote( form.get( "jb_dst_planet", "0" ) ) )
                    moon_to = cgi.escape( urllib.unquote( form.get( "jb_dst_moon", "0" ) ) )
                    owner = cgi.escape( urllib.unquote( form.get( "jb_owner", "" ) ) )
                    password = cgi.escape( urllib.unquote( form.get( "jb_password", "" ) ) )
                    comment = cgi.escape( urllib.unquote( form.get( "jb_comment", "" ) ) )
                    #(self, sys_from, planet_from, moon_from, sys_to, planet_to, moon_to, owner, password, comment="")
                    jb_temp = JumpBridge( sys_from, planet_from, moon_from, sys_to, planet_to, moon_to, owner, password, comment="" )
                    #jb_temp = JumpBridge( s[0], s[1].split("-")[0], s[1].split("-")[1], s[2], s[3].split("-")[0], s[3].split("-")[1], s[4], s[5], comment )
                    global lock_jump_bridges
                    global jump_bridges
                    lock_jump_bridges.acquire() ### XXX LOCK ACQUIRE XXX
                    jump_bridges.append( jb_temp )
                    pickle.dump( jump_bridges, open("jump_bridges.pkl", "w+") )
                    lock_jump_bridges.release() ### XXX LOCK RELEASE XXX
                    return "jb"
                elif form.has_key('sig_set'):
                    global signatures
                    solar = cgi.escape( urllib.unquote( form.get( "sig_sys", "" ) ) )
                    signature = cgi.escape( urllib.unquote( form.get( "sig_signature", "?-?" ).upper() ) )
                    # TODO: SECURITY!! FIXME
                    if form.has_key('button'):
                        if form['button']=='DELETE':
                            safely_delete_signature( (solar, signature) )
                            self.sig_cleanup() # side effect. TODO: move it somewhere else? Separate thread?
                            return "signature"
                        elif form['button']=='EDIT':
                            key = (solar, signature)
                            try:
                                oldsig = signatures[key]
                            except KeyError:
                                return ("signature-missing", key)
                            return ("signature-edit", oldsig)
                    # TODO: wrapper for getting things from the form. Also: max lengths.
                    planet = cgi.escape( urllib.unquote( form.get( "sig_planet", "" ) ) )
                    typee = cgi.escape( urllib.unquote( form.get( "sig_type", "" ) ) )
                    name = cgi.escape( urllib.unquote( form.get( "sig_name", "" ) ) )
                    comment = cgi.escape( urllib.unquote( form.get( "sig_comment", "" ) ) )
                    creator = cgi.escape( urllib.unquote( form.get( "sig_creator", "" ) ) )
                    timee = cgi.escape( urllib.unquote( form.get( "sig_time", "" ) ) )
                    if timee=="":
                        timee = time.time()
                    else:
                        timee = float(timee) # throws. Nobody cares, though.
                    newsig = Signature( solar, signature, planet, typee, name, comment, creator, timee )
                    lock_signatures.acquire() ### XXX LOCK ACQUIRE XXX
                    signatures[ (solar, signature) ] = newsig
                    pickle.dump( signatures, open("signatures.pkl", "w+") )
                    lock_signatures.release() ### XXX LOCK RELEASE XXX
                    return ("signature", newsig)
                elif form.has_key('admin'):
                    if form.has_key('password_set_1') and len( form['password_set_1'] )>0:
                        if self.security_query("password_set_1"):
                            temp = cgi.escape( urllib.unquote( form['password_set_1'] ) )
                            if temp in g_password.itervalues():
                                out("please choose other password<BR>")
                            else:
                                g_password[1] = temp
                        else:
                            out("unauthorized!")
                    if form.has_key('security_policy_set') and len( form['security_policy_set'] )>0:
                        if self.security_query("security_policy_set"):
                            global security_policy
                            temp = cgi.escape( urllib.unquote( form['security_policy_set'] ) )
                            if not temp.isdigit():
                                out("security policy must be a number!")
                            else:
                                temp = int( temp )
                                if temp>3 or temp<0:
                                    out("security policy must be a number greater than -1 and less than 4!")
                                else: 
                                    security_policy = temp
                        else:
                            out("unauthorized!")
                    if form.has_key('password_set_2') and len(form['password_set_2'])>0:
                        if self.security_query("password_set_2"):
                            temp = cgi.escape( urllib.unquote( form['password_set_2'] ) )
                            if temp in g_password.itervalues():
                                out("please choose other password<BR>")
                            else:
                                g_password[2] = temp
                        else:
                            out("unauthorized!")
                    if self.security_query("fleet_invite_set"):
                        global g_fleet_invite
                        if not form.has_key('fleet_invite_set'):
                            g_fleet_invite = ""
                        else:
                            temp = cgi.escape( urllib.unquote( form['fleet_invite_set'] ) )
                            if temp.startswith("http://gang:") and len(temp)<30 and len(temp)>13 and temp[len("http://gang:"):].isdigit():
                                g_fleet_invite = temp[len("http://gang:"):]
                            else:
                                out("malformed fleet invite url! it must be like \"http://gang:1234567890123456789012345\"")
                    return "admin"
                elif form.has_key('button'):
                    if form['button']=='SHIP LOST':
                        return "loss"
                    if form['button']=='LOGOUT':
                        return "logout"
                # defaults are set here
                if form.has_key('ship'):
                    proto = cgi.escape( urllib.unquote( form['ship'] ) )
                    proto = string.capwords(proto).replace("Mark Iv", "Mark IV").replace("Mark Iii", "Mark III").replace("Mark Ii", "Mark II")
                    if not proto in ship_list:
                        out( self.red_text("INVALID SHIP TYPE! Please correct ship type and press UPDATE") + "<BR><BR>")
                    else:
                        ship = proto
                if form.has_key('can_scout'):
                    player.can_scout = True
                else:
                    player.can_scout = False
                if form.has_key('cyno'):
                    player.cyno = True
                else:
                    player.cyno = False
                if form.has_key('cloak'):
                    player.cloak = True
                else:
                    player.cloak = False
                if form.has_key('rr'):
                    player.rr = True
                else:
                    player.rr = False
                if form.has_key('range') and form['range'].isdigit():
                    player.range = int( form['range'] )
                else:
                    player.range = 0
                if form.has_key('dd') and form['dd'].isdigit():
                    player.dd = int( form['dd'] )
                else:
                    player.dd = -1
        #print ship, warPlayerList.has_key(player.name), warPlayerList
        if ship == "Unknown" and warPlayerList.has_key(player.name):
            ship = warPlayerList[player.name].ship
        #print ship
        if ship == "Unknown":
            haskey = False
            try:
                haskey = pilotList.getPilot(player.name).serverData.data.has_key('ship')
            except Exception:
                pass
            if haskey:
                ship = pilotList.getPilot(player.name).serverData.data['ship']
        player.ship = ship
        return None

    @classmethod
    def get_loca_struct(self, di_players, filter2):
        return self.get_loca_helper(di_players, filter2, location_level=True)

    @classmethod
    def get_small_loca_struct(self, di_players, filter2):
        return self.get_loca_helper(di_players, filter2, location_level=False)

    @classmethod
    def get_loca_helper(self, di_players, filter2, location_level):
        """ returns a model for make_fleet_table. Model structure:
        if location_level:
            loca = dict(solar:
                              dict(location:
                                            dict(ship_class:
                                                    list(player)
                                                )
                                  )
                        )
        else:
            loca = dict(solar:
                              dict(ship_class:
                                      list(player)
                                  )
                        )
        """
        loca = {}
        for playername in di_players:
            player = di_players[playername]
            if not self.filterPlayer(filter2, player):
                continue
            if not loca.has_key(player.solar):
                loca[player.solar] = {}
            given_solar = loca[player.solar]
            if location_level:
                if not loca[player.solar].has_key(player.location):
                    loca[player.solar][player.location] = {}
                shiptype_container = loca[player.solar][player.location]
            else:
                shiptype_container = given_solar
            ship_class = getShipClass(player.ship)
            if not shiptype_container.has_key(ship_class):
                shiptype_container[ship_class] = []
            shiptype_container[ship_class].append( player )
        return loca

    @classmethod
    def get_ship_systems_roles(cls, loca_small):
        """ returns a list of tuples(sys_name, string like 5 classA, 3 classB, 2 classC) """
        for sys_name in loca_small.iterkeys():
            sys_dict = loca_small[sys_name]
            result = {}
            for ship_type in Handler.li_shiptypes_ordered: # cls?
                if sys_dict.has_key(ship_type):
                    ship_role = get_ship_role(ship_type)
                    li_those_kind = sys_dict[ship_type]
                    if not result.has_key(ship_role):
                        result[ship_role] = 0
                    result[ship_role] += len(li_those_kind)
            buff = []
            for role in result:
                buff.append( "%s %s" % (result[role], role ) )
            yield sys_name, ", ".join(buff)

    def get_loca_system_order(self, loca):
        """ returns a list of systems ordered by the shipcount in systems and (if equal) sys name """
        system_sorter = []
        for sys_name, system_dict in loca.iteritems():
            sys_count = 0
            for loc_name, loc_dict in system_dict.iteritems():
                for shipclass_name, shipclass_list in loc_dict.iteritems():
                    sys_count += len(shipclass_list)
            system_sorter.append( (sys_count, sys_name) )
        system_sorter.sort()
        system_sorter.reverse()
        system_sorter2 = map( lambda x: x[1], system_sorter )
        return system_sorter2

    def make_fleet_table(self, di_players, mode=1, filter2=[lambda x: True]):
        """ outputs a html fleet table """
        # mode:
        # 1 - one line per ship type
        # 2 - one line per ship type, whole system into a single bucket
        # 3 - one line per pilot with ship type
        output = []
        loca = self.get_loca_struct(di_players, filter2)
        system_sorter2 = self.get_loca_system_order(loca)

        output.append("<TABLE cellspacing=0 cellpadding=6 border=1>")
        for sys_name in system_sorter2:
            sys_dict = loca[sys_name]
            output.append(" <TR>\n")
            #td_buff = self.link("showinfo:5//" + getSolarID(sys_name), txt(sys_name))
            td_buff = "<A HREF=\"showinfo:5//" + getSolarID(sys_name) + "\">" + txt(sys_name) + "</A>"
            td_buff = td_buff + "<BR>"
            td_buff = td_buff + self.link("/details/"+prepare(sys_name), txt("(filter)"))
            output.append( self.td( td_buff, "rowspan=%s" % (len(sys_dict),) ) )
            skip = True
            for loc_name, loc_dict in sys_dict.iteritems():
                closetr = True
                if skip:
                    skip = False
                    closetr = False
                else:
                    output.append(" <TR>\n")
                output.append( self.td( "%s" % (txt(shorten_station_name(loc_name, sys_name)),) ) )
                output.append("<TD>\n")
                buff = []
                buff2 = []
                for typeorder in self.li_shiptypes_ordered:
                    if loc_dict.has_key(typeorder):
                        shipclass_name = typeorder
                        shipclass_list = loc_dict[typeorder]
                        buff.append( "%s&nbsp;%s" % (len(shipclass_list), txt(shipclass_name) ))
                        for player in shipclass_list:
                            buff2.append("%s&nbsp;<A HREF=\"showinfo:1377//%s\">%s</A><BR>" % (txt(player.ship), player.ID, txt(player.name)))
                output.append(", ".join(buff) + "<HR>")
                output.append( "\n".join(buff2) )
                output.append("</TD>\n")
                if closetr:
                    output.append(" </TR>\n")
            output.append(" </TR>\n")
        output.append("</TABLE><BR>")
        return "".join(output)

    def make_war_summary(self, warPlayerList):
        li_shipcounts = []
        total = 0
        for myshiptype in self.li_shiptypes_ordered:
            count = self.getPilotsAmount(warPlayerList, self.get_player_filters("shiptype", shiptype=myshiptype) )
            if count>0:
                li_shipcounts.append( str(count) + " " + myshiptype )
            total+=count
        return "Ships tracked: " + str(total) + " (%s)" % ", ".join(li_shipcounts) + "<BR>"

    def make_fleet_invite(self, player): # TODO: mount it somewhere ?
        global g_fleet_invite
        temp = ""
        if len(g_fleet_invite)>0:
            temp = "http://gang:" + g_fleet_invite
        out("Fleet invite: <INPUT NAME=\"fleet_invite_set\" TYPE=TEXT SIZE=30 VALUE=\"%s\" MAXLENGTH=30><BR>" % temp )

    def make_sig_view(self, player, signature_to_edit=None):
        self.conditional_output(True, False, "sig_set", self.make_sig_set_view, player, signature_to_edit)
        self.conditional_output(True, False, "sig_view", self.make_sig_list, player)

    def make_sig_list(self, player):
        global signatures
        out = self.out
        result = []
        sig_sorter = {}
        for index in signatures:
            sig = signatures[index]
            sig_sorter[sig.solar] = sig_sorter.get(sig.solar, [])
            sig_sorter[sig.solar].append( sig )
        allow_delete = self.security_query("sig_set")
        result.append("<TABLE cellspacing=0 cellpadding=6 border=1>")
        result.append( self.tr( [self.td( item ) for item in ["System", "Type", "Signature", "Nearest Planet", "Name", "Comment", "Creator", "Created", "Delete"] ] ) )
        lastdt = self.get_last_dt_datetime()
        if player.solar in sig_sorter:
            sig_sorter[player.solar].sort( key=lambda s: str.lower(s.signature) ) # sort by signature name
            for sig in sig_sorter[player.solar]:
                result.append( self.make_sig_row(sig, lastdt, allow_delete, highlight=True) )
        for solar in sorted(sig_sorter):
            li_sig = sig_sorter[solar]
            if solar==player.solar:
                continue
            for sig in sorted(li_sig, key=lambda s: s.creation_time): # sort by creation time
                result.append( self.make_sig_row(sig, lastdt, allow_delete) )
        result.append("</TABLE>")
        result.append("<BR>")
        return "\n".join( result )

    def sig_cleanup(self):
        # TODO: where this should be executed from... Once after every downtime, I think...
        global signatures
        global lock_signatures
        delete_before = self.get_dt_datetime( daysago=5 )
        for index in signatures.keys(): # without .keys() this crashes! interesting case
            sig = signatures[index]
            ts = datetime.utcfromtimestamp( sig.creation_time )
            if (delete_before-ts)>=timedelta(0):
                safely_delete_signature( index )

    def get_last_dt_datetime(self):
        return self.get_dt_datetime()

    def get_dt_datetime(self, daysago=0):
        nowtuple = datetime.utcnow().timetuple() # y m d H m s
        day = date( *nowtuple[:3] )
        if nowtuple[3] < 12:
            day = day - timedelta( days=1 )
        if daysago:
            day = day - timedelta( days=daysago )
        dt = datetime( *day.timetuple()[:3] ) + timedelta( hours=12 )
        return dt

    def make_sig_row(self, sig, lastdt, allow_delete=False, highlight=False):
        # TODO: cleanup
        result = []
        solar = txt( sig.solar )
        if highlight:
            solar = "<font color=\"green\">" + solar + "</font>"
        result.append( self.td( solar ) )
        sig_properties = [
            sig.typee,
            sig.signature,
            sig.planet,
            sig.name,
            sig.comment,
            sig.creator
        ]
        result.append( " ".join( [self.td( txt(item) ) for item in sig_properties] ))
        ts = datetime.utcfromtimestamp( sig.creation_time )
        datestamp = txt( ts.strftime("%m.%d&nbsp;%H:%M") )

        if (lastdt-ts)>=timedelta(0):
            datestamp = "<font color=\"red\">" + datestamp + "</font>"

        result.append( self.td( datestamp ) )
        if allow_delete:
            result.append( "<TD>" )
            result.append( self.make_form_header( "sig_set" ) )
            result.append( "<INPUT TYPE=HIDDEN NAME=\"sig_sys\" VALUE=\"%s\">" % str(sig.solar) )
            result.append( "<INPUT TYPE=HIDDEN NAME=\"sig_signature\" VALUE=\"%s\">" % str(sig.signature) )
            result.append( "<INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"EDIT\">&nbsp;" )
            result.append( "<INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"DELETE\">" )
            result.append( "</FORM>" )
            result.append( "</TD>" )
        return self.tr("".join( result ))

    def make_sig_set_view(self, player, signature_to_edit=None):
        result = []
        if signature_to_edit:
            result.append("Edit:")
            sig = signature_to_edit
            default_solar = sig.solar
            default_signature = sig.signature
            default_planet = sig.planet
            default_typee = sig.typee
            default_name = sig.name
            default_comment = sig.comment
            creation_time = sig.creation_time
            creator = sig.creator
        else:
            result.append("Add new:")
            default_solar = player.solar
            default_signature = False
            default_planet = False
            default_typee = ( "Gravimetric", "Ladar", "Magnetometric", "Radar", "Wormhole", "Other" )
            default_name = False
            default_comment = False
            creation_time = False
            creator = player.name
        li_form_field = []
        li_form_field.append( ("System", "sig_sys", 32, default_solar) )
        li_form_field.append( ("Nearest planet", "sig_planet", 2, default_planet) )
        li_form_field.append( ("Signature", "sig_signature", 7, default_signature) )
        li_form_field.append( ("Type", "sig_type", 1333, default_typee ) )
        li_form_field.append( ("Name", "sig_name", 255, default_name) )
        li_form_field.append( ("Comment", "sig_comment", 255, default_comment) )
        li_form_field.append( ("CREATOR", "sig_creator", -1, creator) )
        if creation_time:
            li_form_field.append( ("CREATIONTIME", "sig_time", -1, creation_time) )
        result.append( self.make_form( "sig_set", li_form_field ) )
        return "\n".join( result )

    def make_form_header(self, form_type):
        result = []
        result.append("<FORM METHOD=\"POST\">") # ACTION=\"../cgi-bin/test.py\"
        result.append(" <INPUT TYPE=HIDDEN NAME=\"%s\" VALUE=\"1\">" % form_type)
        result.append(" <INPUT TYPE=HIDDEN NAME=\"password\" VALUE=\"%s\">" % self.password)
        return "\n".join(result)

    def make_form_table(self, li_form_field):
        result = []
        result.append("<TABLE cellspacing=0 cellpadding=6 border=1>")
        for printable_name, internal_name, maxlen, default_value in li_form_field:
            if maxlen==-1:
                result.append( "<INPUT TYPE=\"HIDDEN\" NAME=\"%s\" VALUE=\"%s\">" % (internal_name, default_value ) )
            else:
                result.append("<TR>")
                result.append(" <TD>%s</TD>" % txt(printable_name) )
                value = ""
                if isinstance(default_value, tuple):
                    result.append( "<TD>" )
                    for selection in default_value:
                        result.append( "<INPUT type=\"radio\" name=\"%s\" value=\"%s\">%s " % (internal_name, selection, txt(selection) ) )
                    result.append( "</TD>" )
                else:
                    if default_value!=False:
                        value = " VALUE=\"%s\"" % default_value
                    result.append(" <TD><INPUT NAME=\"%s\" TYPE=TEXT SIZE=%s MAXLENGTH=%s %s></TD>" % (internal_name, maxlen+1, maxlen, value) )
                result.append("</TR>" )
        result.append("</TABLE>")
        return "\n".join( result )

    def make_form(self, form_type, li_form_field):
        result = []
        result.append( self.make_form_header( form_type ) )
        result.append( self.make_form_table( li_form_field ) )
        result.append(" <INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"APPLY\">")
        result.append("</FORM>")
        return "\n".join( result ) #.replace("\n", "") # FIXME \n's hurt?

    def make_jb_set_view(self, player):
        result = []
        result.append("Add new:")
        li_form_field = []
        li_form_field.append( ("Source system", "jb_src_sys", 32, player.solar) )
        li_form_field.append( ("Source planet", "jb_src_planet", 2, False) )
        li_form_field.append( ("Source moon", "jb_src_moon", 2, False) )
        li_form_field.append( ("Destination system", "jb_dst_sys", 32, player.solar) )
        li_form_field.append( ("Destination planet", "jb_dst_planet", 2, False) )
        li_form_field.append( ("Destination moon", "jb_dst_moon", 2, False) )
        li_form_field.append( ("Password", "jb_password", 32, False) )
        li_form_field.append( ("Owner", "jb_owner", 16, False) )
        li_form_field.append( ("Comment", "jb_comment", 255, False) )
        result.append( self.make_form( "jb_set", li_form_field ) )
        return "\n".join( result )

    def make_jb_view(self, player):
        self.conditional_output(True, False, "jb_set", self.make_jb_set_view, player)
        self.conditional_output(True, False, "jb_view", self.make_jb_list)

    def make_jb_list(self):
        result = []
        result.append("<UL>")
        global jump_bridges
        jb_sorter = {}
        for jb in jump_bridges:
            jb_sorter[jb.owner] = jb_sorter.get(jb.owner, [])
            jb_sorter[jb.owner].append( jb )
        for jb_owner, jb_list in jb_sorter.iteritems():
            for jb in jb_list:
                try:
                    result.append("<LI>From %s (%s-%s) to %s (%s-%s), pass: \"%s\", owned by %s %s</LI>" % ( solar_link(jb.sys_from), jb.planet_from, jb.moon_from, solar_link(jb.sys_to), jb.planet_to, jb.moon_to, jb.password, jb.owner, jb.comment) )
                except KeyError: # TODO: FIXME
                    result.append("<LI>From %s (%s-%s) to %s (%s-%s), pass: \"%s\", owned by %s %s</LI>" % ( jb.sys_from, jb.planet_from, jb.moon_from, jb.sys_to, jb.planet_to, jb.moon_to, jb.password, jb.owner, jb.comment) )
        result.append("</UL>")
        return "\n".join( result )

    def make_admin_form(self, warPlayerList, player):
        out = self.out
        out("<HR>")
        out("<FORM METHOD=\"POST\">") # ACTION=\"../cgi-bin/test.py\"
        global g_password
        #if self.security_query("password_set_1"):
        #    out("User password: <INPUT NAME=\"password_set_1\" TYPE=TEXT SIZE=20 VALUE=\"%s\" MAXLENGTH=20><BR>" % g_password[1])
        if self.security_query("password_set_2"):
            out("Admin password: <INPUT NAME=\"password_set_2\" TYPE=TEXT SIZE=20 VALUE=\"%s\" MAXLENGTH=20><BR>" % g_password[2])
        if self.security_query("security_policy_set"):
            out("Security policy: <INPUT NAME=\"security_policy_set\" TYPE=TEXT SIZE=3 VALUE=\"%s\" MAXLENGTH=1><BR>" % self.getSecurityPolicy() )
        if self.security_query("fleet_invite_set"):
            global g_fleet_invite
            temp = ""
            if len(g_fleet_invite)>0:
                temp = "http://gang:" + g_fleet_invite
            out("Fleet invite: <INPUT NAME=\"fleet_invite_set\" TYPE=TEXT SIZE=30 VALUE=\"%s\" MAXLENGTH=30><BR>" % temp )
        out(" <INPUT TYPE=HIDDEN NAME=\"admin\" VALUE=\"1\">")
        out(" <INPUT TYPE=HIDDEN NAME=\"password\" VALUE=\"%s\">" % self.password)
        out(" <INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"APPLY\">")
        out("</FORM>")
        out("<HR>")
        out("Security policy modes:<BR>")
        out("0 - full access for everyone (but admin panel is only for admins)<BR>")
        out("1 - limited access (only losses and numbers of cyno/cloak/scout are visible for non-admins. No tables for non-admins.)<BR>")
        out("2 - very limited access (everything is hidden for non-admins)<BR>")
        out("<HR>")
        out("Fleet invitation HOWTO:<BR>")
        out("1. Post fleet invitation on the channel<BR>")
        out("2. Right-click it and select \"COPY URL\"<BR>")
        out("3. Right-click on the Fleet Invite form field above and select \"PASTE\"<BR>")
        out("4. Click \"APPLY\" button on the form<BR>")
        out("<HR>")
        out("Logged admins:<BR>")
        self.conditional_output(True, False, "admin_list", self.make_simple_table_helper, warPlayerList, "admins")
        out("<HR>")
        self.conditional_output(True, False, "stats_image", self.make_stats_img)

    def make_stats_img(self):
        return "<IMG SRC=\"/img/stats.png?%s\"><BR>" % self.password

    def make_map2_img(self):
        if self.password=="":
            return "<IMG SRC=\"/img/map.png\"><BR>"
        else:
            return "<IMG SRC=\"/img/map.png?%s\"><BR>" % self.password

    def make_autopilot_form(self, player):
        out = self.out
        out("<FORM METHOD=\"POST\">")
        out(" From: <INPUT NAME=\"sys_from\" TYPE=TEXT SIZE=32 MAXLENGTH=32 VALUE=\"%s\"><BR>" % player.solar)
        out(" To: <INPUT NAME=\"sys_to\" TYPE=TEXT SIZE=32 MAXLENGTH=32><BR>")
        out(" <INPUT TYPE=HIDDEN NAME=\"autopilot\" VALUE=\"1\">")
        out(" <INPUT TYPE=HIDDEN NAME=\"password\" VALUE=\"%s\">" % self.password)
        out(" <INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"FIND\">")
        out("</FORM><BR>")

    def validate_and_guess_system(self, given_sys, type_sys):
        out = self.out
        if not is_valid_sys_name(given_sys):
            if len(given_sys)==0:
                out("Empty \"%s\" system<BR><BR>" % type_sys)
                return False
            li_match = guess_solars_name(given_sys)
            if len(li_match)==0:
                out("Invalid \"%s\" system<BR><BR>" % type_sys)
                return False
            elif len(li_match)>1:
                out("Invalid \"%s\" system, may be one of %s <BR><BR>" % ( type_sys, ", ".join( map(solar_link, li_match) ) ) )
                return False
            else:
                return li_match[0]
        else:
            return given_sys

    def make_road_plan(self, sys_from, sys_to):
        out = self.out
        sy = {}
        for given_sys, type_sys in [ (sys_from, "from"), (sys_to, "to") ]:
            result = self.validate_and_guess_system( given_sys.strip(), type_sys )
            if result==False:
                return
            sy[type_sys] = result
        out( find_route(sy["from"], sy["to"]).replace("\n", "<BR>") )
        out("<BR><BR>")

    def make_ship_form(self, player):
        defaultship = player.ship
        out = self.out
        out("<FORM METHOD=\"POST\" name=\"x\" onsubmit=\"return f(this)\">")
        out("Your ship: <INPUT NAME=\"ship\" TYPE=TEXT SIZE=15 VALUE=\"%s\" MAXLENGTH=25>&nbsp;&nbsp;" % defaultship)
        global g_fleet_invite
        if len(g_fleet_invite)>0:
            out("<A HREF=\"gang:" + g_fleet_invite + "\">" + txt("Fleet invitation") + "</A>")
        if not self.path.startswith("/map"):
            out("<BR>")
        #out("<INPUT NAME=\"dd\" TYPE=TEXT SIZE=2 VALUE=\"%s\" MAXLENGTH=1>DD&nbsp;proof&nbsp;&nbsp;&nbsp;&nbsp;" % player.dd)

        menulist = self.get_menu_items(player)
        for m in menulist:
            check = ""
            if m[0]:
                check = "CHECKED"
            out("%s <INPUT NAME=\"%s\" TYPE=checkbox %s>&nbsp;&nbsp;" % (m[1], m[2], check))

        out("<INPUT TYPE=HIDDEN NAME=\"password\" VALUE=\"%s\">" % self.password)
        out("<INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"UPDATE\">")
        out("<INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"SHIP LOST\">")
        #out("Optimal <INPUT NAME=\"range\" TYPE=TEXT SIZE=4 VALUE=\"%s\" MAXLENGTH=3>km&nbsp;&nbsp;" % player.range)
        out("</FORM><BR>")

    @classmethod
    def get_menu_items(cls, player):
        menulist = []
        menulist.append( (player.cloak, "Cloak", "cloak") )
        menulist.append( (player.cyno, "Cyno", "cyno") )
        menulist.append( (player.can_scout, "Scout", "can_scout") )
        #menulist.append( (player.rr, "RR", "rr") )
        return menulist

    def printPilotsAmount(self, warPlayerList, player_filters):
        return str( self.getPilotsAmount(warPlayerList, player_filters) )

    @classmethod
    def getPilotsAmount(cls, warPlayerList, player_filters):
        counter = 0
        for charname in warPlayerList:
            if isinstance(warPlayerList, dict):
                player = warPlayerList[charname]
            elif isinstance(warPlayerList, list) or isinstance(warPlayerList, tuple):
                player = charname
            if cls.filterPlayer(player_filters, player):
                counter += 1
        return counter

    def make_war_menu(self, warPlayerList):
        out = self.out
        for item in ["simple", "details", "map"]:
            if self.path == "/"+item:
                out("<B>%s</B>     " % (item,) )
            else:
                out(self.link("/" + item, item) + "     ")
        out(" | ")
        for item in ["cloak", "cyno", "can_scout", "losses"]:
            if self.path == "/"+item:
                out("<B>%s</B>&nbsp;(" % item )
            else:
                out( self.link("/" + item, item) + "&nbsp;(" )
            if item=="losses":
                self.conditional_output(True, True, "top_summary_"+item, self.printPilotsAmount, losses, self.get_player_filters("default", (0, 6*60*60) ) )
            else:
                self.conditional_output(True, True, "top_summary_"+item, self.printPilotsAmount, warPlayerList, self.get_player_filters(item) )
            out(")     ")
        security_items = []
        security_items.append( ("autopilot", "autopilot") )
        security_items.append( ("jb_view", "jb") )
        security_items.append( ("sig_view", "sig") )
        security_items.append( ("map_image", "map2") )
        security_items.append( ("admin_panel", "admin") )
        for right, item in security_items:
            if self.security_query(right):
                out(" | ")
                if self.path == "/"+item:
                    out("<B>%s</B>     " % (item,) )
                else:
                    out(self.link("/" + item, item) + "     ")
        out("<FORM METHOD=\"POST\" name=\"x\" onsubmit=\"return f(this)\">") #  ACTION=\"../cgi-bin/test.py\"
        out("| <INPUT TYPE=SUBMIT NAME=\"button\" VALUE=\"LOGOUT\">")
        out("</FORM>")
        out("<BR>")

# \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\ WAR PANEL /////////////////////////////////////

def getSolarDict():
    f = open("solarsystems.csv", "r")
    lines = f.readlines()
    f.close()
    systems = {}
    for line in lines:
        if line=='' or line=='\n':
            continue
        line = line[:-1] # \n thingy
        splited = line.split(',')
        systems[splited[0]] = splited[1]
    return systems

def getSolarID(system_name):
    global solar_dict
    return solar_dict.get(system_name, "Unknown")

def solar_link(sys_name):
    return "<A HREF=\"showinfo:5//" + getSolarID(sys_name) + "\">" + txt(sys_name) + "</A>"

def guess_solars_name(guess):
    global systems_regions
    result = []
    for sys_name in systems_regions.keys():
        if sys_name.lower().startswith( guess.lower() ):
            result.append( sys_name )
    return result

def getShipDict():
    f = open("statki4.csv", "r")
    lines = f.readlines()
    ships = {}
    ship_list = []
    for line in lines:
        if line=='' or line=='\n':
            continue
        line = line[:-1] # \n thingy
        splited = line.split(',')
        ships[splited[0]] = splited[1:]
        for shiptype in splited[1:]:
            ship_list.append(shiptype)
    f.close()
    return ships, ship_list

def getShipClass(item):
    for ship_type in ship_types:
        if item in ship_types[ship_type]:
            return ship_type
    return "ERROR:getShipClass()"

def preLoadCorporation(pilotList, loginData, cacheObject):
    newPilotsServerData = getMemberDataCache(loginData[0], loginData[1], loginData[2], loginData[3], cacheObject)
    nicklist = set()
    for pilot in newPilotsServerData:
        pilotnick = pilot['nick']
        pilotObject = pilotList.getPilot(pilotnick)
        pilotObject.serverData.data = pilot
        nicklist.add(pilotnick)
    return nicklist

def prepare(arg):
    return arg.replace(' ', '%20')

def txt(arg):
    return arg.replace(' ', '&nbsp;')

def shorten_station_name(string, system):
    station_suffix = " (docked)"
    if string.startswith(system):
        string = string[len(system)+1:]
    if not string.startswith("Planet "): # custom station name
        if len(string)>30:
            string = string[:30]
    elif string.endswith(station_suffix):
        string = string[:string.find(station_suffix)]
        #string = string #.replace("Planet", "P").replace("Moon", "m") # for small resolutions?
        spl = string.split(" - ")
        buffer = []
        n = 2
        for x in spl[len(spl)-1].split(" "): 
            if len(x)>=n:
                buffer.append( x[:n] )
            else:
                buffer.append( x )
        output = spl[:len(spl)-1]
        output.append( " ".join(buffer) )
        string = " - ".join(output)
        string = string + station_suffix
    return string

def ago_string(ago):
    ago = int(ago)
    killed_ago_seconds = ago % 60
    killed_ago_minutes = ago % 3600 / 60
    killed_ago_hours = ago / 3600
    buffer = ""
    if killed_ago_hours>0:
        buffer = buffer + str(killed_ago_hours) + "h "
    if killed_ago_minutes>0:
        buffer = buffer + str(killed_ago_minutes) + "min "
    if killed_ago_seconds>0:
        buffer = buffer + str(killed_ago_seconds) + "s "
    return buffer

def cache_is_cold(condition_query_name):
    global cache
    if not cache.has_key(condition_query_name):
        return True
    elif cache[condition_query_name][0]-time.time()<0:
        return True
    else:
        return False

def cache_fill(type, data):
    global cache
    if not cache.has_key(type):
        cache[type] = {}
    if type=="stats_image": # url
        cache_time = 3600
    elif type=="stats_image_data":
        cache_time = 30 # changes every 60s anyway
    elif type=="map_image": # url
        cache_time = 3600
    elif type=="map_image_data":
        cache_time = 10 # expensive
    elif type=="war_summary":
        cache_time = 20
    elif type=="admin_list":
        cache_time = 20
    elif type=="sig_set" or "sig_view": # TODO: both disabled?
        cache_time = 0
    else: # thrown an exception?
        cache_time = 5
    cache[type][0] = time.time()+cache_time
    cache[type][1] = data

def cache_get(type):
    global cache
    return cache[type][1]

def __add_ship_class_roles(main_dict, role, li_types):
    for shipclass in li_types:
        ship_roles[shipclass] = role

def get_ship_role(ship_type):
    global ship_roles
    return ship_roles[ship_type]

def get_region(sys_name):
    return systems_regions[sys_name]

def is_valid_sys_name(sys_name):
    return sys_name in systems_regions

class SolarSystem:
    NOT_VISITED = 100
    TOUCHED = 101
    VISITED = 102
    GATE = 1001
    JB = 1002
    def __init__(self, sys_name):
        self.name = sys_name
        self.parent = None
        self.links = set()

    def add_link(self, sys_name, link_type):
        self.links.add( sys_name )

    def add_links(self, set_links, link_type):
        self.links.update( set_links )

def safely_delete_signature( key ):
    global lock_signatures
    global signatures
    lock_signatures.acquire() ### XXX LOCK ACQUIRE XXX
    try:
        del signatures[ key ]
    except KeyError:
        pass # it was already deleted
    pickle.dump( signatures, open("signatures.pkl", "w+") )
    lock_signatures.release() ### XXX LOCK RELEASE XXX

def find_route(sys_from, sys_to, use_jb=True):
    # the cost of this algorithm could be somewhat reduced if We would start seeking routes from both ends
    # the Cormen/Rivest book doesn't suggest it though, and for current number of nodes it's fast enough
    global g_jumps
    global jump_bridges
    global systems_regions
    systems = {}
    for sys_name in systems_regions.keys():
        ss = SolarSystem( sys_name )
        if use_jb:
            for jb in jump_bridges:
                if sys_name in jb:
                    ss.add_link( jb.other_side_than( sys_name ), SolarSystem.JB )
        systems[sys_name] = ss
    for sys_name, set_jumps in g_jumps.iteritems():
        systems[sys_name].add_links( set_jumps, SolarSystem.GATE )
    systems[sys_from].parent = -1
    fifo = [ systems[sys_from] ]
    while len(fifo)>0:
        src = fifo.pop(0)
        for dst_name in src.links:
            dst = systems[dst_name]
            if dst.parent==None:
                dst.parent = src
                fifo.append( dst )
                if dst_name==sys_to:
                    fifo = []
                    break
    path = []
    sys_current = systems[sys_to]
    while sys_current!=sys_from:
        sys_name_old = sys_current.name
        sys_current = sys_current.parent
        path.append( sys_name_old )
        if sys_current==None or sys_current==-1:
            break
    path.reverse()
    result = solar_link( path[0] )
    while len(path)>=2:
        sys_src = path.pop(0)
        sys_dst = path[0]
        info = ",\n"
        for jb in jump_bridges:
            if sys_src==jb.sys_from and sys_dst==jb.sys_to:
                info = " (JB %s owned by %s)\n" % ( jb.exact_from(), jb.owner )
                break
            elif sys_dst==jb.sys_from and sys_src==jb.sys_to:
                info = " (JB %s owned by %s)\n" % ( jb.exact_to(), jb.owner )
                break
        result+=info + solar_link(sys_dst)
    return result

#{{{ global ship_roles, ship_roles_order 
global ship_roles, ship_roles_order
ship_roles = {}
__add_ship_class_roles( ship_roles, "Caps", [ "TITAN", "Mothership", "DREAD", "CAPS"] )
__add_ship_class_roles( ship_roles, "BS", [ "Black Ops", "Marauder", "BS", "Command" ] )
__add_ship_class_roles( ship_roles, "Support", [ "BC", "HAC", "HIC", "Recon", "Logistic", "Cruiser", "DICTOR", "Destroyer", "Covert", "CEP", "Frigate", "Electronic Attack", "Assault"] )
__add_ship_class_roles( ship_roles, "Other", [ "Mining Barge", "Exhumer", "Shuttle", "EGG", "Capital Industrial Ship", "Jump Freighter", "Freighter", "NOOBSHIP", "Transport", "Industrial"] )
__add_ship_class_roles( ship_roles, "Unknown", [ "Unknown" ] )
ship_roles_order = [ "Caps", "BS", "Support", "Other", "Unknown" ]
#}}}

#{{{ global locks, cache, lockable_items 
global locks, cache, lockable_items
locks = {}
cache = {}
lockable_items = [ "disconnected_table", "war_summary", "losses_table", "fleet_table", "stats_image_data", "stats_image", "map_image_data", "map_image", "admin_list", "jb_view", "jb_set", "sig_view", "sig_set" ] # note: We append some below
for item in ["cloak", "cyno", "can_scout", "losses"]:
    lockable_items.append( "top_summary_" + item )
for item in lockable_items:
    locks[item] = Lock()
#}}}

#{{{ ship_types, ship_list 
global ship_types, ship_list
ship_types, ship_list = getShipDict()
solar_dict = getSolarDict()
#}}}

#{{{ compensated_rates{}
global compensated_rates
compensated_rates = {}
#}}}

#{{{ global warPlayerList{} 
global lock_warPlayerList, warPlayerList
lock_warPlayerList = Lock()
if __name__ == '__main__':
    lock_warPlayerList.acquire() ### XXX LOCK ACQUIRE XXX
    if os.path.isfile("warPlayerList.pkl"):
        warPlayerList = pickle.load( open("warPlayerList.pkl") )
    else:
        warPlayerList = {}
    lock_warPlayerList.release() ### XXX LOCK RELEASE XXX
#}}}

#{{{ global losses[] 
if __name__ == '__main__':
    global losses # TODO: own lock
    lock_warPlayerList.acquire() ### XXX LOCK ACQUIRE XXX
    if os.path.isfile("losses.pkl"):
        losses = pickle.load( open("losses.pkl") )
    else:
        losses = []
    lock_warPlayerList.release() ### XXX LOCK RELEASE XXX
#}}}

#{{{ global g_fleet_invite"" 
global g_fleet_invite
g_fleet_invite = ""
#}}}

#{{{ global security_policy, allow_global_refresh_rate_change
global security_policy
security_policy = 0
global allow_global_refresh_rate_change
allow_global_refresh_rate_change = False
#}}}

#{{{ global signatures 
# TODO: move it to a loader function
global signatures
signatures = {}
global lock_signatures
lock_signatures = Lock()
if __name__ == '__main__':
    lock_signatures.acquire() ### XXX LOCK ACQUIRE XXX
    if os.path.isfile("signatures.pkl"):
        signatures = pickle.load( open("signatures.pkl") )
    lock_signatures.release() ### XXX LOCK RELEASE XXX
#}}}

#{{{ global jump_bridges 
# TODO: move it to a loader function
global jump_bridges
jump_bridges = [] # set?
global lock_jump_bridges
lock_jump_bridges = Lock()
if __name__ == '__main__':
    lock_jump_bridges.acquire() ### XXX LOCK ACQUIRE XXX
    if os.path.isfile("jump_bridges.pkl"):
        jump_bridges = pickle.load( open("jump_bridges.pkl") )
    lock_jump_bridges.release() ### XXX LOCK RELEASE XXX
#
# TODO: hack
#for line in file( "jb.tsv", "r" ):
#    #sys_from, planet_from, moon_from, sys_to, planet_to, moon_to, comment=""
#    #TM-0P2	6-6	68FT-6	6-5	-A-	rip	napierdala!
#    if line.startswith("#") or len( line.strip() )==0:
#        continue
#    line = line.replace("\n", "")
#    s = line.split("\t")
#    comment = ""
#    if len(s)>=7:
#        comment = s[6]
#    jb_temp = JumpBridge( s[0], s[1].split("-")[0], s[1].split("-")[1], s[2], s[3].split("-")[0], s[3].split("-")[1], s[4], s[5], comment )
#    jump_bridges.append( jb_temp )
#}}}

#{{{ global g_jumps, systems_regions
if __name__ == '__main__':
    global g_jumps, systems_regions
    g_jumps = {}
    db = Db_connection()
    for sys_from, sys_to in db.get_jumps( "*" ):
        g_jumps[sys_from] = g_jumps.get( sys_from, set() )
        g_jumps[sys_from].add( sys_to )
        g_jumps[sys_to] = g_jumps.get( sys_to, set() )
        g_jumps[sys_to].add( sys_from )
    systems_regions = {}
    for region, id, sysname in db.get_region_id_sysname("*"):
        systems_regions[sysname] = region
    db.close()
#}}}

#{{{ global pilotList 
global pilotList
pilotList = PilotList()
if __name__ == '__main__':
    hddnicks = os.listdir(os.getcwd() + '/PilotCustomData')
    i=0
    while i<len(hddnicks):
        hddnicks[i] = hddnicks[i][:-4] # -4 is for the file extension
        i+=1
    set_hddnicks = set( hddnicks )
else:
    set_hddnicks = set( )
#}}}

#{{{ load api data from corporations 
global cacheObject
cacheObject = CacheObject()
loadednicks = set()
if __name__ == '__main__':
    #loadednicks = loadednicks.union( preLoadCorporation(pilotList, LoginData.get("Corporation Name"), cacheObject) )
    #loadednicks = loadednicks.union( preLoadCorporation(pilotList, LoginData.get("Other Corporation Name"), cacheObject) )
    #set_left_ally = set_hddnicks.difference(loadednicks)
    # We make a new object for those who are not in our data collection but are in fact in the corporation. They just joined the corp, it seems.
    for i in set_hddnicks.difference(loadednicks):
        pilotList.getPilot(i).serverData.data["corpname"] = None
#}}}

#{{{ g_stats.start() 
if __name__ == '__main__':
    global g_stats, g_run
    g_run = True
    g_stats = Stats()
    g_stats.start()
#}}}

#{{{ start the HTTP Server 
if __name__ == '__main__':
    PORT = 8001
    httpd = ThreadedHTTPServer(("", PORT), Handler)
    print "serving at port", PORT, "..."
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "exiting... "
        g_run = False
        g_stats.join()
    print "end"
#}}}

# /////////////////////////////////////// section PANEL \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
# \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\ section PANEL /////////////////////////////////////

