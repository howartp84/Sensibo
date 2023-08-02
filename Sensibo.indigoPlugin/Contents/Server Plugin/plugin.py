#! /usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
# Copyright (c) 2016, Perceptive Automation, LLC. All rights reserved.
# SEPCIAL THANK YOU TO EVERYONE WHO HAS EVER WRITTEN A PLUGIN FOR INDIGO
# AS THIS WAS MY MAIN PLACE OF UNDERSTANDING THE STRUCTURE!
################################################################################


################################################################################
# Imports
################################################################################
import indigo
import socket
import logging
import requests
import simplejson as json
################################################################################
# Globals
################################################################################
sensiboPodNameList = list()

_SERVER = 'https://home.sensibo.com/api/v2'
_SLEEP = 15
_SENSIBOSERVERDOWN = False


################################################################################
class Plugin(indigo.PluginBase):
	########################################
	# Class properties
	########################################
	def logmessage(self, message, logtype, isPluginError):

		if (isPluginError):
			self.errorLog(message)
		else:
			if (logtype == 1):
				indigo.server.log(message)
			else:
				self.debugLog(message)

		#if self.logLevel =="1":
			#indigo.server.log(unicode(message),  type=self.pluginDisplayName + ' Debug', isError=False)

		#if isPluginError == True:
			#indigo.server.log(unicode(message),  type=self.pluginDisplayName + ' Error', isError=True)



	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.logLevel = pluginPrefs.get("pluginloglevel", "0")
		self.apikey = pluginPrefs.get('apikey', None)
		self.stopThread = False
		self._runSensibo = False #No point starting until we're configured

		self.logmessage(u'Entered: Func init',0,False)
		self.logmessage(u'Sensibo API Key is %s' % (self.apikey),0, False )
		self.logmessage(u'Plugin Debug Log is %s' % (self.logLevel),0, False )

	########################################
	def startup(self):
		self.logmessage(u'Entered: Func startup',0,False)
		self.updateAllSensiboLists()

	########################################
	def deviceStartComm(self, dev):
		dev.stateListOrDisplayStateIdChanged()
		podID = dev.pluginProps['devicetype']
		dev.updateStateOnServer("podID",podID)

	########################################
	def updateAllSensiboLists(self):
		self.logmessage(u'Entered: Func updateAllSensiboLists',0,False)
		#this function will do something
		if self.apikey is None:
			self.logmessage(u'No API Key Set - Unable to continue',1,True)
			#self.log("No API has been set - please use the plugin config page to set the API Key",0)
			errorText = u"No Api Key Set - please use the plugin config to set the API Key"
			#self.errorLog(errorText)
			#self.lastErrorMessage=errorText
			return

		#continue to get the Sensibo device list
		self.getSensiboPods()
		self._runSensibo = True		#Now we can let runConcurrentThread() do its thing

	#######################################
	def getSensiboPods(self):
		self.logmessage(u'Entered: Func getSensiboPods',0,False)

		try:

			sensiboPods = self.getPods() #Get devices from API
			self.logmessage("sensiboPods: {}".format(sensiboPods),0,False)

			for pod in sensiboPods:
				podID = pod['id']
				podRoom = pod['room']['name'].title()
				podModel = pod['productModel'].title()
				if (podModel == "Airq"):
					podModel = "AirQ"
				if (podModel == "Skyplus"):
					podModel = "SkyPlus"
				podIdentify = "{} ({})".format(podRoom,podModel)
				self.logmessage(u'Found device: {} ({})'.format(podRoom,podModel),1,False)
				#sensiboPodNameList.append([sensiboPods[room], room])   #List of ['RnoKsTMg','Dining Room']
				sensiboPodNameList.append([podID, podIdentify])   #List of ['RnoKsTMg','Dining Room']


		except requests.exceptions.Timeout:
			errorText = u"Failed to retreive data from Sensibo - check settings and retry."
			# Don't display the error if it's been displayed already.
			if errorText != self.lastErrorMessage:
				#self.errorLog(errorText)
				self.logmessage(u'Request timeout while talking to Sensibo',1,True)
				self.logmessage(errorText,1,true)
				# Remember the error.
				self.lastErrorMessage = errorText

		except requests.exceptions.ConnectionError:
			errorText = u"Failed to connect to home.sensibo.com - Check Sensibo is working"
			# Don't display the error if it's been displayed already.
			if errorText != self.lastErrorMessage:
				#self.errorLog(errorText)
				self.logmessage(u'Connection error while talking to sensibo',1,true)
				self.logmessage(errorText,1,true)
				# Remember the error.
				self.lastErrorMessage = errorText
				return

		except Exception, e:
			self.logmessage(u'Unable to obtain data from Sensibo ' + unicode(e),1,True)

	########################################
	def shutdown(self):
		self.logmessage(u'Entered: Func shutdown - Requested to shutdown BYE!',1,False)
		self._runSensibo = False

	########################################
	def runConcurrentThread(self):
		self.logmessage(u'Entered: Func runConcurrentThread',0,False)
		#self.logmessage(u'Starting Sensibo Update',0,False)
		try:
			while True:
				if (self._runSensibo):
					self.updatesensibo()
				self.sleep(_SLEEP)
		except self.StopThread:
			self.debugLog("Stopping Sensibo plugin")
			#self.shutdown()

		except Exception, e:
			 self.logmessage(u'Plugin Stopping.  Reason = %s' % (e) ,0,True)

	def updatesensibo(self):
		self.logmessage(u'Entered: Func update sensibo',0,False)
		#prId = "com.duncangrant.indigoplugin.sensibo"

		if _SENSIBOSERVERDOWN == False:
			for dev in indigo.devices.iter("self"):
					############################################################################################
					# Get The current sensibo device unitid from the list of devices belonging to this plugin  #
					# this value was stored as a device property during the device config validation method.   #
					# SEE closedDeviceConfigUi for details.													#
					############################################################################################
				try:
					if (dev.deviceTypeId == "Sensibodevice" and dev.enabled):
						devProps = dev.pluginProps
						devName = dev.name

						podID = devProps['devicetype']
						self.logmessage(u'Updating Sensibo Pod: {} ({})'.format(podID,devName),0,False)

 						newStateList = []

						if podID == "":
							continue
						dataResponse = self.pod_data(podID)																	#List[] of one or more Field responses
						self.logmessage(u'Data Received ({})  {}'.format(podID,dataResponse),0,False)

						for podDataField in dataResponse:
							podData = dataResponse[podDataField]
							#self.logmessage("podData {}: {} ".format(podDataField,podData),1,False)

							if (podDataField == "productModel"):
								newStateList.append({'key':'model', 'value':str(podData)})

							podStatesToParseF = ["temperature","humidity","targetTemperature","nativeTargetTemperature"]
							for stateF in podStatesToParseF:
								if (stateF in podData):
									#self.logmessage(u'Updating Device State {}: {}'.format(stateF,float(podData[stateF])) ,1,False)
									newStateList.append({'key':stateF, 'value':float(podData[stateF]), 'decimalPlaces': 1})
#								newStateList.append({'key':stateF, 'value':"", 'decimalPlaces': 1})

							podStatesToParseS = ["fanLevel","mode","temperatureUnit","nativeTemperatureUnit","swing"]
							for stateS in podStatesToParseS:
								if (stateS in podData):
									#self.logmessage(u'Updating Device State {}: {}'.format(stateS,str(podData[stateS])) ,1,False)
									newStateList.append({'key':stateS, 'value':str(podData[stateS])})
#								newStateList.append({'key':stateS, 'value':""})

							podStatesToParseB = ["motion","on"]
							for stateB in podStatesToParseB:
								if (stateB in podData):
									if stateB == "on":
										#self.logmessage(u'Updating Device State {}: {}'.format("power",bool(podData["on"])) ,1,False)
										newStateList.append({'key':"power", 'value':bool(podData["on"])})
									else:
										#self.logmessage(u'Updating Device State {}: {}'.format(stateB,bool(podData[stateB])) ,1,False)
										newStateList.append({'key':stateB, 'value':bool(podData[stateB])})
#								newStateList.append({'key':'power', 'value':""})
#								newStateList.append({'key':stateB, 'value':""})

						#End For()

#						acResponse = self.pod_ac_state(podID)
#						self.logmessage(u'AC Response Returned :' + unicode(acResponse),1,False)
#
#						#acState = acResponse['acState']
#						acState = acResponse[0]['acState']
#
#						self.logmessage(u'AC State:' + unicode(acState),1,False)
#
#						acStatesToParseF = ["targetTemperature","nativeTargetTemperature"]
#						for stateF in acStatesToParseF:
#							if (stateF in acState):
#								self.logmessage(u'Updating Device State {}: {}'.format(stateF,float(acState[stateF])) ,1,False)
#								newStateList.append({'key':stateF, 'value':float(acState[stateF]), 'decimalPlaces': 1})
#
#						acStatesToParseS = ["fanLevel","mode","temperatureUnit","nativeTemperatureUnit","swing"]
#						for stateS in acStatesToParseS:
#							if (stateS in acState):
#								self.logmessage(u'Updating Device State {}: {}'.format(stateS,str(acState[stateS])) ,1,False)
#								newStateList.append({'key':stateS, 'value':str(acState[stateS])})
#
#						acStatesToParseB = ["on"]
#						for stateB in acStatesToParseB:
#							if (stateB in acState):
#								if stateB == "on":
#									self.logmessage(u'Updating Device State {}: {}'.format("power",bool(acState["on"])) ,1,False)
#									newStateList.append({'key':"power", 'value':bool(acState["on"])})
#								else:
#									self.logmessage(u'Updating Device State {}: {}'.format(stateB,bool(acState[stateB])) ,1,False)
#									newStateList.append({'key':stateB, 'value':bool(acState[stateB])})

						#dev.updateStateOnServer("fanLevel",acresult["fanLevel"])
						#dev.updateStateOnServer("power",bool(acresult["on"]))
						#dev.updateStateOnServer("mode",acresult["mode"])
						#if acresult["mode"] != "fan":
							#dev.updateStateOnServer("temperatureUnit",acresult["temperatureUnit"])
							#dev.updateStateOnServer("targetTemperature",acresult["targetTemperature"])

						#allStatesParsed = podStatesToParseB + podStatesToParseF	+ podStatesToParseS + acStatesToParseB + acStatesToParseF + acStatesToParseS
						#This won't work as we aren't looping the data states, we're looping what we're looking for!

						newStateList.append({'key':"online", 'value':True})
						dev.updateStatesOnServer(newStateList)

				except Exception, e:
					self.logmessage(u'Error:  Reason = %s' % (e) ,0,True)

		else:

			self.logmessage(u'Sensibo service is not online.  Will retry later',0,False)
			for dev in indigo.devices.iter("self"):
				 #Sensibo Server is offline so we cannot do much about it.
				 #mark all devicea as offline until the server is back online.
				 dev.updateStateOnServer("online",False)


	################################################################################
	# METHOD IS CALLED FROM INDIGO AFTER THE USER CLICKS SAVE ON THE DEVICE CONFIG #
	################################################################################
#This function was defined twice
#	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
#		self.logmessage(u'Entered: Func validateDeviceConfigUI ' + unicode(valuesDict),1,False)
#		return (True, valuesDict)

	#### RETURN THE LIST OF DEVICE FOUND FOR THIS USERS API
	def deviceListGenerator(self, filter="", valuesDict=None, typeId="", targetId=0):
		self.logmessage(u'Entered: Func deviceListGenerator',1,False)
		return sensiboPodNameList

	def _get(self, path, ** params):
		self.logmessage(u'Entered: Func _get',0,False)
		params['apiKey'] = self.apikey
		try:
			# See if the newValue is a number.
			response = requests.get(_SERVER + path, params = params)
			response.raise_for_status() #Throws HTTPError error if HTTP >= 400
			self.debugLog("DATA for {}: {}".format(path,response.json()))
			_SENSIBOSERVERDOWN = False
			return response.json()
		except ValueError:
			# This isn't a number, don't try to make it one.
			_SENSIBOSERVERDOWN = True
			self.logmessage(u'Sensibo API is not responding at this time',0,True)
			pass



	def _patch(self, path, data, ** params):
		params['apiKey'] = self.apikey
		response = requests.patch(_SERVER + path, params = params, data = data)
		response.raise_for_status()
		return response.json()

	def getPods(self):
		#result = self._get("/users/me/pods", fields="id,room,remoteFlavor")
		#result = self._get("/users/me/pods", fields="*")
		result = self._get("/users/me/pods", fields="id,productModel,room")
		#self.logmessage("getPods:  {}".format(result),0,False)
		#return {x['room']['name']: x['id'] for x in result['result']}
		return result['result']

	def pod_data(self, podID):
		self.logmessage(u'Getting data(measurement) for {}'.format(podID),0,False)
		#result = self._get("/pods/%s/measurements" % podID)
		result = self._get("/pods/%s" % podID, fields="id,room,productModel,measurements,acState")
		return result['result']

	def pod_ac_state(self, podID):
		result = self._get("/pods/%s/acStates" % podID, limit = 1, fields="status,reason,acState")
		return result['result']
		#return result['result'][0]['acState']

	def _post(self, path, data, ** params):
		params['apiKey'] = self.apikey
		response = requests.post(_SERVER + path, params = params, data = data)
		response.raise_for_status()
		return response.json()

	def pod_change_ac_state(self, podID, powerstate, target_temperature, mode, fan_level):
		self._post("/pods/%s/acStates" % podID,
					   json.dumps({'acState': {"on": powerstate, "targetTemperature": target_temperature, "mode": mode, "fanLevel": fan_level}}))

	# Closed Device Configuration
	########################################
	def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, deviceId):
		self.logmessage(u'Entered: Func closeDeviceConfigUi :' + unicode(valuesDict),0,False)

		# If the user didn't cancel the changes, take any needed actions as a result of the changes made.
		if not userCancelled:
			# Configuration was saved.  Rebuild the device if needed.
			device = indigo.devices[deviceId]
			devProps = device.pluginProps
			devProps['unitId'] = valuesDict['devicetype'] #deviceType is the Pod's "ID"
			device.replacePluginPropsOnServer(devProps)
			self.debugLog("Setting the unitId in device properties " + valuesDict['devicetype']  )
			self.debugLog("Recalling this unitId to see if it has stored " + devProps['unitId'] )
			self.debugLog("Recalling this unitId to see if it has stored " + device.pluginProps['unitId'] )

	# Validate Device Configuration
	########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, deviceId):
		self.logmessage(u'Entered: Func validateDeviceConfigUi',0,False)
		errorsDict = indigo.Dict()
		errorsDict['showAlertText'] = ""
		isError = False


		return (True, valuesDict)

	def validateActionConfigUi(self, valuesDict, typeId, deviceId):
		self.logmessage(u'Entered: Func validateActionConfigUi',0,False)
		errorsDict = indigo.Dict()
		errorsDict['showAlertText'] = ""
		isError = False
		device = indigo.devices[deviceId]

		upower = device.states['power']
		if valuesDict.get('unitpower', "") == True:
			if valuesDict.get('mode', "") == "":
				isError = True
				errorsDict['mode'] = u"Please select a mode."
				errorsDict['showAlertText'] += errorsDict['mode']
				return (False, valuesDict, errorsDict)
			if valuesDict.get('mode', "") == "":
				isError = True
				errorsDict['fanlevel'] = u"Please select a fan level."
				errorsDict['showAlertText'] += errorsDict['fanlevel']
				return (False, valuesDict, errorsDict)
			if valuesDict.get('mode', "") == "":
				isError = True
				errorsDict['targettemperature'] = u"Please select the Target Temperature."
				errorsDict['showAlertText'] += errorsDict['targettemperature']
				return (False, valuesDict, errorsDict)

		return (True, valuesDict)

	def closedPrefsConfigUi(self, valuesDict, UserCancelled):
		indigo.server.log("Config CLOSED " + unicode(valuesDict),  type=self.pluginDisplayName + ' Info', isError=False)

		self.logLevel = valuesDict['pluginloglevel']
		self.apikey = valuesDict['apikey']
		indigo.server.log("Logging Now %s" % self.logLevel ,  type=self.pluginDisplayName + ' Info', isError=False)
		self.updateAllSensiboLists()	#Fetch the devices etc from API before user starts creating Indigo devices.
		return (True, valuesDict)

##########################################################################################################################
# ACTION CODE TO HANDLE THE ACTIONS.XML FILE
##########################################################################################################################

# Set Power
########################################
	def setPower(self, action, device):
		self.logmessage(u'Entered: Func setPower :',0,False)

		upower = action.props.get('unitpower', False)

		devProps = device.pluginProps
		podID = devProps['devicetype']
		targetSource = action.props.get('targetSource', False)
		self.logmessage(u'targetSource :' + targetSource,0,False)

		if _SENSIBOSERVERDOWN==False:
			if upower == "False":
				mode = device.states['mode'] #Current mode; ie no change
				fanlevel = device.states['fanLevel']
				targetTemperature = device.states['targetTemperature']
				self.pod_change_ac_state(podID, False, int(targetTemperature), "%s" % mode, "%s" % fanlevel)
				device.updateStateOnServer("power",False)
			if upower == "True":
				#let's get the additional parameters needed to setup the AC unit
				mode = action.props.get('mode', False)
				fanlevel = action.props.get('fanlevel', 'low')
				targetTemperature=19
				if targetSource == "custom":
					targetTemperature = action.props.get('targetTemperature', 20)
					self.logmessage(u'Setting temperature to custom value :' + unicode(targetTemperature),1,False)
					self.pod_change_ac_state(podID,True, int(targetTemperature), "%s" % mode, "%s" % fanlevel)
				elif targetSource == "variable":
					#targetTemperature = action.props.get('targettemperature', 20)
					targetVarId = action.props.get('targetVariable', False)
					targetTemperature = indigo.variables[int(targetVarId)].value
					self.logmessage(u'Setting temperature to variable value :' + unicode(targetTemperature),1,False)
					self.pod_change_ac_state(podID,True, int(targetTemperature), "%s" % mode, "%s" % fanlevel)

				#Lets update the local device states so that any triggers don't get fired accidently due to
				#time between refresh states
				device.updateStateOnServer("fanLevel",fanlevel)
				device.updateStateOnServer("power",True)
				device.updateStateOnServer("mode",mode)
				device.updateStateOnServer("targetTemperature",int(targetTemperature))
		else:
			self.logger.info("Cannot perform action right now.  Sensibo Servers are offline.")



	#Request To Toggle the current power state of the device.
	def togglePower(self, action, device):
		self.logmessage(u'Entered: Func togglePower',0,False)
		devProps = device.pluginProps
		podID = devProps['devicetype']
		currentpowerstate = device.states['power']

		if currentpowerstate == True:
			mode = device.states['mode']
			fanlevel = device.states['fanLevel']
			targetTemperature = device.states['targetTemperature']
			self.pod_change_ac_state(podID,False, int(targetTemperature), "%s" % mode, "%s" % fanlevel)
			device.updateStateOnServer("power",False)
		else:
			mode = device.states['mode']
			fanlevel = device.states['fanLevel']
			targetTemperature = device.states['targetTemperature']
			self.pod_change_ac_state(podID,True, int(targetTemperature), "%s" % mode, "%s" % fanlevel)
			device.updateStateOnServer("power",True)

	#Request To Toggle the current power state of the device.
	def setFan(self, action, device):
		self.logmessage(u'Entered: Func setFan ' + unicode(action),0,False)

		devProps = device.pluginProps
		podID = devProps['devicetype']
		currentpowerstate = device.states['power']
		fanlevel = action.props.get('fanlevel', False)

		if currentpowerstate == True:
			mode = device.states['mode']
			targetTemperature = device.states['targetTemperature']
			self.pod_change_ac_state(podID,True, int(targetTemperature), "%s" % mode, "%s" % fanlevel)
			device.updateStateOnServer("fanLevel",fanlevel)
		else:
			mode = device.states['mode']
			targetTemperature = device.states['targetTemperature']
			self.pod_change_ac_state(podID,False, int(targetTemperature), "%s" % mode, "%s" % fanlevel)
			device.updateStateOnServer("fanLevel",fanlevel)



