
"""Generate Driving Directions:

	FMEProcessRoutes and supporting classes to generate driving directions based
	on input BusRoutes.  No output features are generated.  Directions are printed 
	to the logger object.
	
	Roads and BusStops are also required to produce driving directions.
	
	FEATURENAME attribute must be added to each input to separate ROAD from ROUTE.
	Bus route features do not need to be pre-sorted, and are sorted by this script.
	
	Exceptions are raised for missing attributes, roads & routes that are not lines,
	and route segments that to not meet.

	Date:   2013 Jan 17
	Author: Andrew Ross

"""

##############################################################################
import fmeobjects
import math
import sys
import time
import myClasses.busStopName  # formatter for bus stop IDs
		# G:\BusinessIntelligence\Data\Resource\FME\Transformers\myClasses\busStopName.py


##############################################################################
"""Global Variables
	G_LOGGING:                  display logging: true or false
	NEEDED_ROAD_ATTRIBUTES:     list of attributes required in road features
	NEEDED_BUSROUTE_ATTRIBUTES: list of attributes required in bus route features
	NEEDED_BUSSTOP_ATTRIBUTES:  list of attributes required in bus stop features
"""

G_LOGGING=True
NEEDED_ROAD_ATTRIBUTES=('ID','NAME_FULL','RD_CLASS','NAME_ID')
NEEDED_BUSROUTE_ATTRIBUTES=('ID','ORDR','SIDE','ROUTENUM','ROUTENAME','PTRNNUM',  \
		'BCTSYSTEM','BCTREGION','END_STOPID', 'START_STOPID')
NEEDED_BUSSTOP_ATTRIBUTES=('STOPID','STOPNAME','EXCHANGE','PARKNRIDE','AREANAME')


##############################################################################
def logMessage( message, exitStatus=False ):
	"""logMessage: Function to centralize output
	
		Modify this function as required to print to STDOUT or LOG and 
		utilize G_LOGGING or ignore it
	
		input:  string to be displayed
				exitStatus boolean - if true then quit
	"""
	
	if G_LOGGING:
		try:  # if logger not defined then create it
			logMessage.logger
		except:
			logMessage.logger = fmeobjects.FMELogFile()
		logMessage.logger.logMessageString( message )
		if exitStatus: exit()


def listFeatureAttributes( f ):
	"""listFeatureAttributes: return list of attribute:value pairs for given feature
	"""
	attributes = []
	for a in f.getAllAttributeNames():
		attributes.append( "%s:%s" % (a,str(f.getAttribute( a ))))
	return attributes
	

##############################################################################
class RoadIntersection( object ):
	"""RoadIntersection: Class to represent road intersections in the 
	   Intersection table.

	"""

	def __init__( self, roadid,roadnameid,roadClass,azimuth ):
		self.roadID = roadid
		self.nameID = roadnameid
		self.roadClass = roadClass
		self.azimuth = azimuth


##############################################################################
class IntersectionTable( object ):
	"""IntersectionTable: Class to manage table of road intersections

		Given road segment or point added to table, indexed by
		a unique ID generated from point's coordinates.
		(See: RoadSegment.calculatePointID)
		Table used to calculate number of intersecting segments at 
		each road intersection.
	"""

	def __init__( self ):
		self.roadIntersectionArray = {}

	def addRoadSegment( self, s ):
		"""addRoadSegment: add start & end points of given road segment to table
		"""
		self.addRoadPoint( s.startPointID, s.id, s.nameID, s.roadClass, s.startAzimuth )
		self.addRoadPoint( s.endPointID, s.id, s.nameID, s.roadClass, s.endAzimuth )

	def addRoadPoint( self, i, roadid, roadnameid, roadClass, azimuth ):
		if not (i in self.roadIntersectionArray.keys()): self.roadIntersectionArray[i] = {}
		self.roadIntersectionArray[i][roadid] =  \
				RoadIntersection( roadid,roadnameid,roadClass,azimuth )

	def numberOfIntersectingRoads( self, i, roadid=None ):
		"""numberOfIntersectingRoads: Return the number of roads that intersect at 
		   given road intersection.  Do not count 'ramps' or multiple roads with the
		   same roadID
		"""
		#logMessage("IntersectionTable.numberOfIntersectingRoads roadid: %d" % roadid)
		count = 0
		roadIDs = []
		if i in self.roadIntersectionArray.keys(): 
			return len(self.roadIntersectionArray[ i ])
			#logMessage("IntersectionTable.numberOfIntersectingRoads # segments: %d" % len(self.roadIntersectionArray[ i ]))
			for r in self.roadIntersectionArray[ i ].values():
				if (r.roadClass != 'ramp') and (r.nameID not in roadIDs):
					count += 1
					roadIDs.append(r.nameID)
				elif r.nameID == roadid: count += 1
				#logMessage("IntersectionTable.numberOfIntersectingRoads r.nameID: %d" % r.nameID)
				#logMessage("IntersectionTable.numberOfIntersectingRoads r.roadClass: %s" % r.roadClass)
				#logMessage("IntersectionTable.numberOfIntersectingRoads count: %d" % count)
			#logMessage("IntersectionTable.numberOfIntersectingRoads count: %d" % count)
			return count
		else: return 0

	def getRoadAzimuth( self, i, roadid ):
		if (i in self.roadIntersectionArray.keys() ) and (roadid in self.roadIntersectionArray[i].keys() ):
			return self.roadIntersectionArray[i][roadid]
		else : return 0


##############################################################################
class RoadSegment( object ):
	"""RoadSegment: Class to represent a road segments.

		Each input Feature must be a multipoint line, with one or more 
		verticies, and the required attributes.
		For each segment additional attributes are calculated:
		start & end point IDs, start & end direction (azimuth) from
		end point to next point, start & end point compass direction
		(cardinal), and the segment length.
	
		RoadSegment attributes:
			.id (int)
			.name (string)
			.nameID (int)
			.roadClass (string)
			.startPointID (list - generated from coordinates)
			.endPointID (list - generated from coordinates)
			.length (float)
			.startAzimuth (float)
			.endAzimuth (float)
			.startCardinal (string)
			.endCardinal (string)
	"""

	def __init__( self, f ):
		if self.isValidRoadSegment( f) :
			# Set road attributes.
			self.id = int(f.getAttribute('ID'))
			self.name = f.getAttribute('NAME_FULL')
			self.nameID = int(f.getAttribute('NAME_ID'))
			self.roadClass = f.getAttribute('RD_CLASS')
			self.startPointID = self.calculatePointID( f.getCoordinate(0))
			self.endPointID = self.calculatePointID( f.getAllCoordinates()[-1])
			self.length = self.calculateLength( f )
			self.startAzimuth = self.calculateStartAzimuth( f )
			self.endAzimuth = self.calculateEndAzimuth( f )
			self.startCardinal = self.calculateCardinal( self.startAzimuth )
			self.endCardinal = self.calculateCardinal( self.endAzimuth )
		else:
			logMessage("RoadSegment class: unable to load feature %s att:%s" % (str(f), \
					str(f.getAllAttributeNames())), True)

	def isValidRoadSegment( self, f ):
		"""isValidRoadSegment: segment needs to have more than 1 vertex & required attributes
		"""
		
		if f.numCoords() > 1 and ( set( NEEDED_ROAD_ATTRIBUTES ) <= set(f.getAllAttributeNames())) : return True
		else: return False
	def calculatePointID( self, p ):
		return (int(round( p[0] )),int(round( p[1] )))

	def calculateLength( self, f ): 
		totalLength = 0
		pointA = f.getCoordinate(0)
		for pointB in f.getAllCoordinates()[1:]:
			totalLength += math.hypot( pointB[0]-pointA[0],pointB[1]-pointA[1] )
			pointA = pointB
		return totalLength

	def calculateStartAzimuth( self, feature ):
		(x1,y1) = feature.getCoordinate(0)
		(x2,y2) = feature.getCoordinate(1)
		return math.degrees( math.atan2( x2-x1,y2-y1 ) )

	def calculateEndAzimuth( self, feature ):
		(x1,y1) = feature.getAllCoordinates()[-2]
		(x2,y2) = feature.getAllCoordinates()[-1]
		return math.degrees( math.atan2( x2-x1,y2-y1 ) )

	def calculateCardinal( self, angle ):
		return ('north', 'north-east', 'east', 'south-east',  \
				'south', 'south-west', 'west',  \
				'north-west')[ (int( angle +22.5) /45) %8 ]


##############################################################################
class BusRouteSegment( RoadSegment ):
	"""BusRouteSegment: Class to represent bus route segments, extended	from RoadSegment.

		In addition to RoadSegment calculations, the start and end
		points of the segment are switched if the ORDR field has
		been set to '-1'.

		BusRouteSegment attributes:
			.id (int)
			.name (string)
			.startPointID (list - generated from coordinates)
			.endPointID (list - generated from coordinates)
			.length (float)
			.startAzimuth (float)
			.endAzimuth (float)
			.startCardinal (string)
			.endCardinal (string)
			.order (int)
			.roadClass (string)
			.side (int - 0 or -1) 
	"""

	def __init__( self, f ):
		if self.isValidBusrouteSegment( f ):
			#logMessage("BusRoutefeature new: " + ':'.join((
			#		f.getAttribute('ID'), f.getAttribute('ORDR'), f.getAttribute('SIDE'))))
			# Set route attributes.
			self.id = int(f.getAttribute('ID'))
			# Attributes name & roadClass are added from road network.
				# self.name = f.getAttribute('NAME_FULL')
				# self.roadClass = f.getAttribute('RD_CLASS')
			self.startPointID = self.calculatePointID( f.getCoordinate(0))
			self.endPointID = self.calculatePointID( f.getAllCoordinates()[-1])
			self.length = self.calculateLength( f )
			self.startAzimuth = self.calculateStartAzimuth( f )
			self.endAzimuth = self.calculateEndAzimuth( f )
			self.startCardinal = self.calculateCardinal( self.startAzimuth )
			self.endCardinal = self.calculateCardinal( self.endAzimuth )
			self.order = int(f.getAttribute('ORDR'))
			self.side = int(f.getAttribute('SIDE'))
			if self.side == -1:
				# if line reversed swap startPoints, azimuth, and cardinal
				self.startPointID,  self.endPointID  = self.endPointID,  self.startPointID
				self.startAzimuth,  self.endAzimuth  = (self.endAzimuth -180) %360,  (self.startAzimuth -180) %360
				#self.startAzimuth = (self.startAzimuth -180) %360
				#self.endAzimuth = (self.endAzimuth -180) %360
				self.startCardinal = self.calculateCardinal(self.startAzimuth)
				self.endCardinal = self.calculateCardinal(self.endAzimuth)
		else:
			raise("BusRouteSegment class: unable to load feature %s" % str(f))

	def updateAttributes( self, roadSegment ):
		self.name = roadSegment.name
		self.roadClass = roadSegment.roadClass
		self.nameID = roadSegment.nameID

	def isValidBusrouteSegment( self, f ):
		if f.numCoords() > 1 and ( set( NEEDED_BUSROUTE_ATTRIBUTES ) <=  \
				set(f.getAllAttributeNames())) : 
			return True
		else: 
			if f.numCoords() <= 1: 
				raise Exception("RouteSegment.isValidBusrouteSegment: not a line segment")
			errorString=""
			for a in NEEDED_BUSROUTE_ATTRIBUTES:
				if not a in f.getAllAttributeNames():
					errorString += a + " "
			raise Exception ("RouteSegment.isValidBusrouteSegment: Missing attributes: " + errorString)


##############################################################################
class BusRoute( object ):
	"""BusRoute: Class to represent bus routes and generate driving directions.

		Contains route information along with an array of Bus
		Route segments.
		Note segments are sorted before processing and can be 
		added out of order.

		BusRoute attributes:
			.routeID (int)
			.routeName (string)
			.patternNumber (int)
			.bctSystem (string)
			.bctRegion (string)
			.startBusstopID (int)
			.endBusstopID (int)
	"""

	def __init__( self, f ):
		if self.isValidBusRoute( f ):
			#logMessage("New Bus Route: " + ':'.join((  \
			#		f.getAttribute('ROUTENUM'), f.getAttribute('ROUTENAME'),  \
			#		f.getAttribute('PTRNNUM'), f.getAttribute('BCTSYSTEM'),  \
			#		f.getAttribute('BCTREGION'), f.getAttribute('START_STOPID'), \
			#		f.getAttribute('END_STOPID'))))
			self.routeID = int( f.getAttribute('ROUTENUM') )
			self.routeName = f.getAttribute('ROUTENAME')
			self.patternNumber = int(f.getAttribute('PTRNNUM'))
			self.bctSystem = f.getAttribute('BCTSYSTEM')
			self.bctRegion = f.getAttribute('BCTREGION')
			self.startBusstopID = int(f.getAttribute('START_STOPID'))
			self.endBusstopID = int(f.getAttribute('END_STOPID'))
			self.routeSegments = []
		else:
			raise("BusRoute class: unable to load feature %s" % str(f))

	def isValidBusRoute( self, f ):
		if f.numCoords() > 1 and ( set( NEEDED_BUSROUTE_ATTRIBUTES ) <=  \
				set(f.getAllAttributeNames())) : 
			return True
		else: 
			if f.numCoords() <= 1: 
				raise Exception("BusRoute.isValidBusrouteSegment: not a line segment")
			errorString=""
			for a in NEEDED_BUSROUTE_ATTRIBUTES:
				if not (a in f.getAllAttributeNames()):
					errorString += a + " "
			raise Exception ("BusRoute.isValidBusrouteSegment: Missing attributes: " + errorString)

	def addFeature( self,f ):
		self.routeSegments.append( BusRouteSegment( f))

	def addSegment( self, s ):
		self.routeSegments.append( s )
	
	def sortRoute( self ):
		self.routeSegments.sort( key=lambda s: s.order)
	
	def printFormatDistance( self, l ):
		if l < 100: return ", travel %.0f meters" % l
		else: return ", travel %.1f km" % ( l/1000 )

	def getTurnDirection( self, lastSegment, nextSegment, intersectionTable ):
		"""getTurnDirection: return human-printable direction

			Input:  two adjacent segments on the bus route
					table of road intersections indexed by pointID
			Output: human readable string stating how to turn from lastSegment onto nextSegment
					taking into account ramps, direction, topology, etc
		"""

		# angle between input segments
		difference = (nextSegment.startAzimuth - lastSegment.endAzimuth) %360
		
		logMessage("BusRoute.getTurnDirection difference: %s" % str(difference) )
		logMessage("BusRoute.getTurnDirection startAzimuth: %s" % str(nextSegment.startAzimuth) )
		logMessage("BusRoute.getTurnDirection endAzimuth: %s" % str(lastSegment.endAzimuth) )
		
		if lastSegment.endPointID != nextSegment.startPointID:
			logMessage ("ERROR: BusRoute.getTurnDirection: topology problem - segments do not connect", True)

		if lastSegment.roadClass == 'ramp': return "Merge on %s" % nextSegment.name
		if nextSegment.roadClass == 'ramp':
			logMessage("BusRoute.getTurnDirection ramp")
			if intersectionTable.numberOfIntersectingRoads( nextSegment.startPointID, nextSegment.nameID ) <= 2 :
				return "Continue on %s" % nextSegment.name
			if difference > 180: return "Take %s on Left" % nextSegment.name
			if difference < 180: return "Take %s on Right" % nextSegment.name
		
		# road continues but name change at point - only two road segments at intersection
		if intersectionTable.numberOfIntersectingRoads(  \
				nextSegment.startPointID, lastSegment.nameID ) <= 2 :
			logMessage("BusRoute.getTurnDirection only 2 roads")
			if ((difference +50) %360) < 100 : return "Continue on %s" % nextSegment.name
			if difference > 180: return "Turn Left on %s" % nextSegment.name
			if difference < 180: return "Turn Right on %s" % nextSegment.name

		# if less than 10 degree difference -> go straight
		logMessage("BusRoute.getTurnDirection regular intersection")
		if ((difference +25     ) %360) < 50 : return "Continue Straight on %s" % nextSegment.name
		if ((difference +25 -180) %360) < 50 : return "Turn Around on %s" % nextSegment.name
		if difference > 180: return "Turn Left on %s" % nextSegment.name
		if difference < 180: return "Turn Right on %s" % nextSegment.name

	def drivingDirectionsAsString( self, intersectionTable, busStops ):
		"""drivingDirections: return human readable driving directions for this route

			Input:  table of road intersections indexed by pointID
			Output: human readable string stating how to navigate the road segments of this class
		"""
		
		# Ensure all segments sorted before processing.
		self.sortRoute()
		segmentLength = 0.0
		directionString = ""
		# Loop through segments using 'i' as index.
		for i,routeSegment in enumerate(self.routeSegments):
			logMessage("BusRoute.drivingDirectionsAsString name: " + routeSegment.name)
			if i==0:
				directionString = "Starting at %s.  On %s (going %s)" % (  \
						busStops[ self.startBusstopID ],  \
						routeSegment.name, routeSegment.startCardinal)
			# If this is a name change then summarize segment, and get
			# direction for next segment.
			elif routeSegment.name != self.routeSegments[i-1].name:
				directionString += self.printFormatDistance( segmentLength ) + '.  ' # eg: travel xx km
				directionString += self.getTurnDirection(self.routeSegments[i-1],  \
						routeSegment, intersectionTable)  # eg: turn left on XX
				directionString += " (going %s)" % routeSegment.startCardinal
				segmentLength = 0.0
			segmentLength += routeSegment.length

		# End of loop - finish up directions.
		directionString += self.printFormatDistance( segmentLength ) + '.  '
		directionString += "Finish at %s." % busStops[ self.endBusstopID ]
		return directionString
	
	def drivingDirectionsAsFeature( self, intersectionTable, busStops ):
		f = fmeobjects.FMEFeature()
		f.setAttribute( 'ROUTEID', self.routeID )
		f.setAttribute( 'ROUTENAME', self.routeName )
		f.setAttribute( 'PTRNNUM', self.patternNumber )
		f.setAttribute( 'DIRECTIONS', self.drivingDirectionsAsString( intersectionTable, busStops ))
		return f


##############################################################################
class FMEProcessRoutes( object ):
	"""FMEProcessRoutes: Process incoming Bus Route(s) and display human readable directions

		Input:  Bus Route shape file
				Road shape file
		Output: No features are output
				Turn directions for each bus route are sent to Logger
	"""

	def __init__( self ):
		"""__init__: build data structures

			roads{} dictionary of roads indexed by roadID
			busRoutes{} dictionary with one record for each bus route - indexed by routeID/patternNumber
			routeIntersectionNetwork: table of road intersections used by "BusRoute.getTurnDirection"
			busStops{} dictionary: stop id linked to printable name for stop
		"""
		self.roads = {}
		self.busRoutes = {}
		self.routeIntersectionNetwork = IntersectionTable()
		self.busStops = {}

	def input( self, f ):
		"""input: build busRoutes dictionary & routeIntersectionNetwork
		"""
		
		if not (f.getAttribute('FEATURENAME') in ('ROAD','ROUTE','BUSSTOP')):
				logMessage ("FMEProcessRoutes: Unknown FEATURENAME %s %s" % (str(f.getAttribute('FEATURENAME')),str(f)), True)

		featureTypeActions = {
				'ROAD': self.processRoadFeature,
				'ROUTE': self.processRouteFeature,
				'BUSSTOP': self.processBusstopFeature }
		featureTypeActions[f.getAttribute('FEATURENAME')]( f )
		
	def processRoadFeature( self, f ):
		try:
			s = RoadSegment( f )
			self.roads[ s.id ] = s
		except Exception,e:
			logMessage("\n\nFMEProcessRoutes.processRoadFeature: unable to load road.\nException: " + str(e), True)
		#if len(self.roads) % 2000 ==0: logMessage("Road count: " + str(len(self.roads)))


	def processRouteFeature( self, f ):
		#logMessage("processRouteFeature: " + ':'.join((f.getAttribute('ROUTENUM'),f.getAttribute('PTRNNUM'),f.getAttribute('ORDR'))))
		#logMessage("processRouteFeature: trying id:" + str(self.busRouteID(f)))
		try:
			#if Route/Pattern do not exist create new route from feature
			if not (self.busRouteID(f) in self.busRoutes.keys()): self.busRoutes[ self.busRouteID(f) ] = BusRoute( f )
			#add segment to route
			self.busRoutes[ self.busRouteID(f) ].addSegment( BusRouteSegment( f ) )
		except Exception, e:
			logMessage("\n\nFMEProcessRoutes.processRouteFeature: unable to load route segment.\nException :" \
					+ str(e) + "\n" + '\n'.join(listFeatureAttributes(f)), True)
		if len(self.busRoutes) % 20 ==0: logMessage("Route count: " + str(len(self.busRoutes)))
				
	def processBusstopFeature( self, f):
		if set( NEEDED_BUSSTOP_ATTRIBUTES ) <= set(f.getAllAttributeNames()):
			self.busStops[ int(f.getAttribute('STOPID')) ] = myClasses.busStopName.getLongName(  \
					f.getAttribute('STOPNAME'), f.getAttribute('EXCHANGE'),  \
					f.getAttribute('PARKNRIDE'), f.getAttribute('AREANAME'), f.getAttribute('STOPID'))
		else:
			logMessage ("FMEProcessRoutes.processBusstopFeature: unable to load stop %s" % str(f), True)
		#if len(self.busStops) % 500 ==0: logMessage("Busstop count: " + str(len(self.busStops)))

	def close( self ):
		"""close: loop through busRoutes dictionary, print directions for each route
		"""

		logMessage( "\nFMEProcessRoutes.close")
		logMessage( "-- %d routes" % len(self.busRoutes))
		logMessage( "-- %d intersections" % len(self.routeIntersectionNetwork.roadIntersectionArray))
		logMessage( "-- %d bus stops\n" % len(self.busStops))
		
		# loop through road bus route segments
		# add name & road class to route segments
		# add road to intersection table
		for b in self.busRoutes.values():
			for s in b.routeSegments:
				if s.id in self.roads.keys(): 
					s.updateAttributes( self.roads[ s.id ] )
					self.routeIntersectionNetwork.roadIntersectionArray[ s.startPointID ] = {}
					self.routeIntersectionNetwork.roadIntersectionArray[ s.endPointID ] = {}
				else:
					logMessage ("FMEProcessRoutes.close: unable to update BusrouteSegment: id %s, route %s, ptn %s"  \
							% (str(s.id),str(b.routeID),str(b.patternNumber)), True)

		for r in self.roads.values():
			if (r.startPointID in self.routeIntersectionNetwork.roadIntersectionArray.keys())  \
					or (r.endPointID in self.routeIntersectionNetwork.roadIntersectionArray.keys()):
				self.routeIntersectionNetwork.addRoadSegment( r )

							
		logMessage( "-updated routeSegments")
		logMessage( "-- %d routes" % len(self.busRoutes))
		logMessage( "-- %d intersections" % len(self.routeIntersectionNetwork.roadIntersectionArray))
		logMessage( "-- %d bus stops\n" % len(self.busStops))

		for b in self.busRoutes.values():
			logMessage( "\nDriving Directions for: %s (# %d - %d)\n" % (str(b.routeName),b.routeID,b.patternNumber))
			logMessage( b.drivingDirectionsAsString( self.routeIntersectionNetwork, self.busStops ))
			logMessage( "\n" )
			self.pyoutput( b.drivingDirectionsAsFeature(self.routeIntersectionNetwork, self.busStops) )

	def busRouteID( self, f ):
		"""busRouteID: generate id based on routeNumber and patternNumber from given Feature
		
			input:  road feature
			output: list of route number and pattern number
		"""

		return int(f.getAttribute('ROUTENUM')),int(f.getAttribute('PTRNNUM'))

	
