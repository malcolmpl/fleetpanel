#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# Draw.py, part of the FleetPanel
#
# Copyright (c) 2008-2009 Pawe³ 'Reef' Polewicz
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

import Gnuplot
import tempfile
import os
import sys

from pydot import *
from FleetPanel import *
from Db_connection import Db_connection
from JumpBridge import JumpBridge

class Draw:
    @classmethod
    def gnuplot_return(cls, time=30):
        tempfilename = cls.get_temp_file()
        cls.gnuplot(time, infilename="panel.log", outfilename=tempfilename )
        f = open(tempfilename, "r")
        value = f.read()
        f.close()
        os.unlink( tempfilename )
        return value
        
    @classmethod
    def get_temp_file(cls):
        #  since python 2.6 we should use:
        # f = tempfile.NamedTemporaryFile(delete=False)
        # tempfilename = f.name
        f_id, tempfilename = tempfile.mkstemp()
        return tempfilename

    @classmethod
    def gnuplot(cls, time=30, infilename="panel.log", outfilename="gp_test1.png"):
        #g = Gnuplot.Gnuplot(debug=1)
        inf = open( infilename, "r" )
        inf_lines = inf.readlines()
        if len(inf_lines) < time:
            time = len(inf_lines)

        tempfilename = cls.get_temp_file()

        f = open( tempfilename, "w" )
        f.write( "".join(inf_lines[-time:]) )
        f.close()
        cls.draw( time, infilename=tempfilename, outfilename=outfilename)
        os.unlink( tempfilename )
        
    @classmethod
    def draw(cls, time, infilename, outfilename):
        g = Gnuplot.Gnuplot()
        g("set xdata time")
        g("set size 0.6,0.5")
        g("set timefmt \"%Y/%m/%d.%H:%M:%S\"")
        g("set format x \"%M\"")
        #g("set terminal gif")
        g("set terminal png")
        g("set output \"%s\"" % outfilename)
        g.plot(
            Gnuplot.File(infilename, using='1:2', with='lines', title='hits'),
            Gnuplot.File(infilename, using='1:3', with='linesp', title='posts'),
            Gnuplot.File(infilename, using='1:4', with='lines', title='warps'),
            Gnuplot.File(infilename, using='1:5', with='linesp', title='jumps'),
            Gnuplot.File(infilename, using='1:6', with='linesp', title='docks'),
            Gnuplot.File(infilename, using='1:7', with='linesp', title='undocks'),
            Gnuplot.File(infilename, using='1:8', with='lines', title='cached_gets'),
            Gnuplot.File(infilename, using='1:9', with='lines', title='usercount')
        )

    @classmethod
    def __paint_map(cls, system_pairs, systems_regions, ship_systems_roles, jump_bridges, forced_systems, highlighted_systems, outfilename):
        # NOTE: this is where I finished working. The map functionality was experimental and it has already showed that it works, but there were
        # problems with scale, with speed of generating it and with the Eve Game Browser ofcourse.
        color_highlight = "gold"
        #prog = 'dot'
        prog = 'neato'
        #prog = 'fdp'
        #g = Dot() # unusable with neato
        #g = Dot(mode="hier", overlap="orthoyx")
        #g = Dot(overlap="orthoyx", splines="polyline" )

        #g = Dot(splines="compound", overlap="prism") # fdp: super-slow
        #g = Dot(splines="compound", overlap="vpsc") # fdp: super-slow
        #g = Dot(splines="compound", overlap="orthoyx") # fdp: super-slow, but very very pretty
        #g = Dot(splines="true", overlap="prism") # neato: super-slow, but very pretty. fdp not bad too
        #g = Dot(mode="ipsep", overlap="ipsep")
        #g = Dot(overlap="portho") # bad, but usable
        #g = Dot(overlap="vpsc") # good
        #g = Dot(overlap="orthoxy") # good
        #g = Dot(overlap="orthoyx") # better than orthoxy
        g = Dot(overlap="prism") # very clear, very large
        #g.size = "9.5,9.5"
        #g.ratio = "fill"
        g.decorate = True
        g.outputorder = "nodesfirst"
        for link in system_pairs:
            g.add_edge( Edge(dot_str(link[0]), dot_str(link[1]), arrowhead="none", arrowtail="none", style="solid,setlinewidth(2)", color="darkgreen") )

        #arrowType = "open"
        #arrowType = "normal"
        arrowType = "none"
        for jb in jump_bridges:
            g.add_edge(
                Edge(
                    dot_str(jb.sys_from), dot_str(jb.sys_to), color="blue", style="solid", arrowhead=arrowType, arrowtail=arrowType, arrowsize=0.5, labelfloat=False
                )
            )
            #        dot_str(jb.sys_from), dot_str(jb.sys_to), labelfontcolor="red", style="bold", color="blue", arrowhead=arrowType, arrowtail=arrowType, headlabel=jb.exact_from(), taillabel=jb.exact_to(), labelangle=30, labeldistance=2, label=jb.comment, labelfloat=False
        di_all = {}
        for system, str_roles in ship_systems_roles:
            region = systems_regions.get(system, "Unknown")
            if not di_all.has_key(region):
                di_all[region] = []
            di_all[region].append( (system, str_roles) )

        done = set()
        my_regions = {}
        for region, li_systems in di_all.iteritems():
            cluster_region = Cluster( dot_str(region), label=region, color="red", fontcolor="red" )
            my_regions[dot_str(region)] = cluster_region
            #print "region", region
            for sysname, systext in li_systems:
                color = "green"
                if sysname in highlighted_systems:
                    color = color_highlight
                sys_node = Node( dot_str(sysname), label=sysname+"\\n"+systext, style="filled", shape="octagon", color=color )
                cluster_region.add_node(sys_node)
                done.add(sysname)
            for sysname, reg in systems_regions.iteritems():
                if reg==region and not sysname in done:
                    tempsys = Node( dot_str(sysname), label=sysname )
                    cluster_region.add_node(tempsys)

        loose_systems = set( systems_regions.keys() ).difference( done )
        for sysname in loose_systems:
            region = systems_regions[sysname]
            color = "gray"
            if sysname in highlighted_systems:
                color = color_highlight
            sys_node = Node( dot_str(sysname), label=sysname+"\\n", style="filled", color=color)
            my_regions[dot_str(region)] = my_regions.get( dot_str(region), Cluster( dot_str(region), label=region) )
            my_regions[dot_str(region)].add_node(sys_node)
        
        for region_dotted_name, cluster_region in my_regions.iteritems():
            g.add_subgraph(cluster_region)

        #g.write_raw('test-1.dot', prog=prog)
        g.write_png(outfilename, prog=prog)
        #g.write_jpg('test-1.jpg', prog=prog)

    @classmethod
    def draw_map(cls, warPlayerList, filters, jump_bridges, forced_systems, highlighted_systems, outfilename):
        loca = Handler.get_small_loca_struct( warPlayerList, filters )
        solar_list = loca.keys()
        solar_list = set( solar_list )
        solar_list.update( forced_systems )
        solar_list.update( highlighted_systems )

        system_pairs = set()
        jumpable_systems = set()

        db = Db_connection()
        for sys_from, sys_to in db.get_jumps( solar_list ):
            jumpable_systems.add( sys_to )
            if sys_from > sys_to:
                system_pairs.add( (sys_from, sys_to) )
            else:
                system_pairs.add( (sys_to, sys_from) )

        #all_systems = jumpable_systems.union( set(solar_list) ) # a & b
        all_systems = jumpable_systems
        all_systems.update( set(solar_list) ) # a & b
        jump_bridges_out = set()
        should_keep_searching = True
        while should_keep_searching==True:
            should_keep_searching = False
            for jb in jump_bridges:
                has_from = jb.sys_from in all_systems
                has_to = jb.sys_to in all_systems
                if has_from or has_to:
                    if jb not in jump_bridges_out:
                        should_keep_searching = True
                        jump_bridges_out.add( jb ) # add edge
                    # add nodes
                    if has_to and not has_from:
                        all_systems.add( jb.sys_from )
                    elif has_from and not has_to:
                        all_systems.add( jb.sys_to )

        systems_regions = {}
        for region, id, system in db.get_region_id_sysname( all_systems ):
            systems_regions[system] = region
        db.close()

        ship_systems_roles = Handler.get_ship_systems_roles( loca )
        return cls.__paint_map(system_pairs, systems_regions, ship_systems_roles, jump_bridges_out, forced_systems, highlighted_systems, outfilename)

    @classmethod
    def graphviz_return(cls, warPlayerList, filters, jump_bridges, forced_systems=[], highlighted_systems=[]):
        tempfilename = cls.get_temp_file()
        cls.draw_map(warPlayerList, filters, jump_bridges, forced_systems, highlighted_systems, tempfilename)
        f = open(tempfilename, "r")
        value = f.read()
        f.close()
        os.unlink( tempfilename )
        return value

def dot_str(text):
    return text.replace(" ", "_").replace("-", "__")

# test gnuplot
#ala = Draw.gnuplot_return(30)
#print len(ala)

# test dot
#import pickle
#warPlayerList = pickle.load( open("evefleet-server/warPlayerList.pkl") )
#Draw.graphviz_return(warPlayerList, [lambda x: True])

