#!/usr/bin/python
# vim:sw=4:softtabstop=4:expandtab:set fileencoding=ISO8859-2
#
# FleetPanel.py, part of the FleetPanel
#
# Copyright (c) 2009 Dariusz Mikulski email: dariusz.mikulski@gmail.com
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at http://www.opensource.org/licenses/mit-license.php.

import csv
import os

resource_dir = "resources"
wormhole_space_file = "ws.txt"
wormhole_anomaly_file = "ws_anom.txt"

class WormholeSpace:
	def __init__(self):
		self.locus_signature = ""
		self.system_id = ""
		self.constellation_id = ""
		self.region_id = ""
		self.class_type = ""
		self.attributes_modifier = {}
		self.picture_file = ""
					
	def set_detail(self, locus_signature="", system_id="", constellation_id="", region_id="", class_type=""):
		self.locus_signature = locus_signature
		self.system_id = system_id
		self.constellation_id = constellation_id
		self.region_id = region_id
		self.class_type = class_type
		
			
class WormholeAnomaly:
	def __init__(self):
		self.locus_signature = ""
		self.anomaly_name = ""

class Wormhole:
	def __init__(self):
		self.wormhole_space = []
		self.wormhole_anomaly = []
		self.load()
		
	def load(self):
		reader = csv.reader(open(resource_dir + '/' + wormhole_anomaly_file), delimiter=',', quotechar='"')
		for row in reader:
			wa = WormholeAnomaly()
			wa.locus_signature = row[0]
			wa.anomaly_name = row[1]
			self.wormhole_anomaly.append(wa)
			
		reader = csv.reader(open(resource_dir + '/' + wormhole_space_file), delimiter=',', quotechar='"')
		for row in reader:
			ws = WormholeSpace()
			ws.set_detail(row[0], row[1], row[2], row[3], row[4])
			self.wormhole_space.append(ws)
			
		self.check_attributes()
	
	# Fixme! Totally inefficient finction
	def check_attributes(self):
		for wa in self.wormhole_anomaly:
			for ws in self.wormhole_space:
				if wa.locus_signature == ws.locus_signature and wa.anomaly_name:
					additional_file = wa.anomaly_name.replace(' ', '_').lower()
					reader = csv.reader(open(resource_dir + '/' + additional_file + '.txt'), delimiter=',', quotechar='"')
					for row in reader:
						ws.attributes_modifier[row[0]] = row[int(ws.class_type)-1]
					filename = os.path.join(os.path.abspath(''), resource_dir, "pic_" + additional_file + '.png')
					if os.path.exists(filename):
						ws.picture_file = filename
		
