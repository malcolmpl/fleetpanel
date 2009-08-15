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
from types import *

resource_dir = "resources"
wormhole_space_file = "ws.txt"
wormhole_anomaly_file = "ws_anom.txt"
DELIMITER = ','
QUOTECHAR = '"'
SPACECHAR = ' '
UNDERLINECHAR = '_'
TXTFILE_EXTENSION = '.txt'
PNGFILE_EXTENSION = '.png'
PICTURE_PREFIX = 'pic_'

class WhSpaceSystem:
	def __init__(self):
		self.locus_signature = ""
		self.system_id = ""
		self.constellation_id = ""
		self.region_id = ""
		self.class_type = ""
		self.attributes_modifier = {}
		self.picture_file = ""
					
	def set_detail(self, locus_signature, system_id, constellation_id, region_id, class_type):
		self.locus_signature = locus_signature
		self.system_id = system_id
		self.constellation_id = constellation_id
		self.region_id = region_id
		self.class_type = class_type
		
			
class WhAnomalyProperties:
	def __init__(self):
		self.locus_signature = ""
		self.anomaly_name = ""

class Wormhole_Analyzer:
	def __init__(self):
		self._wh_space_systems = []
		self._wh_anomaly_properties = []
		self._load()
		
	def _readfile(self, filename):
		path = os.path.join(os.path.abspath(''), resource_dir, filename)
		return csv.reader(open(path), delimiter=DELIMITER, quotechar=QUOTECHAR)
		
	def _load(self):
		reader = self._readfile(wormhole_anomaly_file)
		for row in reader:
			wa = WhAnomalyProperties()
			wa.locus_signature = row[0]
			wa.anomaly_name = row[1]
			self._wh_anomaly_properties.append(wa)
			
		reader = self._readfile(wormhole_space_file)
		for row in reader:
			ws = WhSpaceSystem()
			ws.set_detail(row[0], row[1], row[2], row[3], row[4])
			self._wh_space_systems.append(ws)
			
		self._check_attributes()
	
	# Fixme! Totally inefficient finction
	def _check_attributes(self):
		for wa in self._wh_anomaly_properties:
			for ws in self._wh_space_systems:
				if wa.locus_signature == ws.locus_signature and wa.anomaly_name:
					additional_file = wa.anomaly_name.replace(SPACECHAR, UNDERLINECHAR).lower()
					reader = self._readfile(additional_file + TXTFILE_EXTENSION)
					for row in reader:
						ws.attributes_modifier[row[0]] = row[int(ws.class_type)-1]
					filename = os.path.join(os.path.abspath(''), resource_dir, PICTURE_PREFIX + additional_file + PNGFILE_EXTENSION)
					if os.path.exists(filename):
						ws.picture_file = filename
		
	def analyze_system(self, system_name):
		if type(system_name) is not StringType:
			return False, None
			
		for whspacesystem in self._wh_space_systems:
			if system_name == whspacesystem.locus_signature:
				return True, whspacesystem
				
		return False, None
