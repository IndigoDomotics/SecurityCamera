#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2014, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo
import os
from os import listdir
from os.path import isfile, join
import sys
import time
import thread
import threading
import subprocess
import datetime
import urllib
import urllib2
import shutil
import math

from datetime import date
from ghpu import GitHubPluginUpdater
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw 
from PIL import ImageChops 
from PIL import ImageEnhance

Intiation = True

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
#
# Image Procedures
#
################################################################################

def getSortedDir(path, srch, start, finish):

	filter_list = []

	name_list = [f for f in listdir(path) if isfile(join(path, f))]
	full_list = [os.path.join(path,i) for i in name_list]
	time_sorted_list = sorted(full_list, key=os.path.getmtime, reverse=True)
	for file in time_sorted_list:
		if file.find(srch) != -1:
			filter_list.append(file) 
	
	if start < 0:
		start = 0

	if finish > len(filter_list):
		finish = len(filter_list)	

	final_list = filter_list[start:finish]
	return final_list

def rmsdiff(im1, im2):
	##################Calculate the root mean square difference of two images
	diff = ImageChops.difference(im1, im2)
	h = diff.histogram()
	sq = (value*((idx%256)**2) for idx, value in enumerate(h))
	sum_of_squares = sum(sq)
	rms = math.sqrt(sum_of_squares/float(im1.size[0] * im1.size[1]))
	return rms

def GetSnapshot(device):
	##################Get single image
	
	nowtime = datetime.datetime.now()
	displaytime = str(nowtime).split(".")[0]
	CameraName = device.pluginProps["CameraName"]
	labeltext = CameraName + " : " + displaytime
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraDir = MainDir + "/" + CameraName
	OrigImage = CameraDir + "/OrigImage.jpg"
	CurrentImage = CameraDir + "/CurrentImage.jpg"
	CameraAddress = device.pluginProps["CameraAddress"]
	CameraUser = device.pluginProps["uname"]
	CameraPwd = device.pluginProps["pwd"]
	URLAddress = "http://" + CameraAddress
	CameraTimeout = device.pluginProps["CameraTimeout"]
	
	#setup image enhancement parameters
	RawImage = device.pluginProps["Raw"]
	CameraRotation = device.pluginProps["CameraRotation"]
	ImageWidth = device.pluginProps["ImageWidth"]
	ImageHeight = device.pluginProps["ImageHeight"]
	BorderWidth = str(device.pluginProps["BorderWidth"])
	BorderColor = device.pluginProps["BorderColor"]
	Brightness = device.pluginProps["Brightness"]
	Contrast = device.pluginProps["Contrast"]
	Sharpness = device.pluginProps["Sharpness"]

	passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
	passman.add_password(None, "http://" + CameraAddress, CameraUser, CameraPwd)
	auth_handler = urllib2.HTTPBasicAuthHandler(passman)
	opener = urllib2.build_opener(auth_handler)
	urllib2.install_opener(opener)
	try:
		jpgfile = urllib2.urlopen("http://" + CameraAddress,timeout=10)
		with open(OrigImage,'wb') as output:
			output.write(jpgfile.read())
			device.updateStateOnServer("CameraState", value="On")
			ImageFound = True
	except:
		ImageFound = False		
	
  	#try:
		#f = urllib.urlopen(URLAddress)
		#with open(OrigImage, "wb") as imgFile:
			#imgFile.write(f.read())
		#device.updateStateOnServer("CameraState", value="On")
	#except:
		#ImageFound = False
	
	if ImageFound:
		device.updateStateOnServer("OfflineSeconds", value="0")
		if str(RawImage) == "False":
			#get image
			img = Image.open(OrigImage)
			#Resize image
			img = img.resize((int(ImageWidth), int(ImageHeight)-15))
			#rotate image
			img = img.rotate(int(CameraRotation))
			#brighten image
			enhancer = ImageEnhance.Brightness(img)
			img = enhancer.enhance(float(Brightness))
			#contrast image
			enhancer = ImageEnhance.Contrast(img)
			img = enhancer.enhance(float(Contrast))
			#sharpen image
			enhancer = ImageEnhance.Sharpness(img)
			img = enhancer.enhance(float(Sharpness))

			#Create label border
			old_size = img.size
			new_size = (old_size[0], old_size[1]+15)
			new_img = Image.new("RGB", new_size, "grey")
			#Add label text 
			draw = ImageDraw.Draw(new_img)
			font = ImageFont.truetype("Verdana.ttf", 8)
			draw.text((5, old_size[1]+3),labeltext,(255,255,255),font=font)
			#Add image to label
			new_img.paste(img, (0,0))	
		
			if int(BorderWidth) > 0:
				old_size = new_img.size
				#Create border
				borderedge = int(BorderWidth)*2
				new_size = (old_size[0]+borderedge, old_size[1]+borderedge)
				final_img = Image.new("RGB", new_size, BorderColor) 
				#Add image to border
				final_img.paste(new_img, (int(BorderWidth),int(BorderWidth)))
			else:
			#Save image without border
				final_img = new_img
		else:
			final_img = Image.open(OrigImage)
	else:
		OfflineSeconds = int(device.states["OfflineSeconds"])
		OfflineSeconds += 1
		device.updateStateOnServer("OfflineSeconds", value=str(OfflineSeconds))
		final_img = Image.open(CurrentImage)

	return final_img

def GetImage(device):
	##################Capture image for video
	
	CameraName = device.pluginProps["CameraName"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraDir = MainDir + "/" + CameraName
	TempImage = CameraDir + "/TempImage.jpg"
	CurrentImage = CameraDir + "/CurrentImage.jpg"
	
	imagedate = time.strftime("%m.%d.%Y.%H.%M.%S")
	NewImage = CameraDir + "/img_" + imagedate + ".jpg"	
	img = GetSnapshot(device)

	imagecount = []
	imagelist = [f for f in listdir(CameraDir) if isfile(join(CameraDir, f))]
	for file in imagelist:
		if file.find("img") != -1:
			imagecount.append(file)
	
	if len(imagecount) > 30:
		sortedList = getSortedDir(CameraDir, "img", 30, 100)
	
	try:	
		for file in sortedList:
			os.remove(file)
	except:
		pass		
	
	img.save(NewImage,optimize=True,quality=70)
	shutil.copy(NewImage, TempImage)
	os.rename(TempImage, CurrentImage)

def MotionCheck(device):
	##################Check for motion

	#Update Threadcount
	localPropsCopy = device.pluginProps
	#localPropsCopy["MotionThreads"] = "1"
	#device.replacePluginPropsOnServer(localPropsCopy)

	#variable setup
	MaxSensitivity = float(device.pluginProps["MaxSensitivity"])
	MinSensitivity = float(device.pluginProps["MinSensitivity"])
	FramesDifferent = int(device.pluginProps["FramesDifferent"])
	MotionReset = int(device.pluginProps["MotionReset"])
	CameraName = device.pluginProps["CameraName"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraDir = MainDir + "/" + CameraName
	CheckMotion = device.pluginProps["CheckMotion"]

	#Set images
	img1 = Image.open(CameraDir + "/CurrentImage.jpg")
	sortedList = getSortedDir(CameraDir, "img", 7, 8)
	img2 = Image.open(sortedList[0])
	ImageDiff = rmsdiff(img1,img2)

	#Average image difference
	ImageAveDiff = device.states["ImageAveDiff"]
	if ImageAveDiff == "":
		ImageAveDiff = "0"
		device.updateStateOnServer("ImageAveDiff", value=0)
	ImageAveDiff = float(ImageAveDiff)
	FramesDiff = device.states["FramesDiff"]

	#Check for change or update average
	if ImageDiff > 0:
		DiffFromAve = float(ImageDiff - ImageAveDiff)
		DiffFromAve = round(DiffFromAve,4)
		device.updateStateOnServer("PixelDiff", value=DiffFromAve)

		if MinSensitivity <= DiffFromAve <= MaxSensitivity:
			FramesDiff = FramesDiff + 1
			device.updateStateOnServer("FramesDiff", value=FramesDiff)
		elif float(ImageDiff) <= float(ImageAveDiff)+10:
			ImageNewAve = round(float(((ImageAveDiff*10) + ImageDiff)/11),4)
			device.updateStateOnServer("ImageAveDiff", value=ImageNewAve)
			device.updateStateOnServer("FramesDiff", value=0)
			MotionSeconds = device.states["MotionSeconds"] + 1
			device.updateStateOnServer("MotionSeconds", value=MotionSeconds)
	else:
		indigo.server.log("Motion Check: " + str(ImageNewAve))
		device.updateStateOnServer("ImageAveDiff", value="0")
		device.updateStateOnServer("MotionSeconds", value=0)

	if CheckMotion:
		#Add label
		imgsize = img1.size
		draw = ImageDraw.Draw(img1)
		font = ImageFont.truetype("Verdana.ttf", 8)
		draw.text(((imgsize[0]-75), (imgsize[1]-15)),str(DiffFromAve),(255,255,255),font=font)
		img1.save(CameraDir + "/CurrentImage.jpg")
		sortedList = getSortedDir(CameraDir, "img", 7, 8)
		img1.save(sortedList[0])
		
	if int(FramesDiff) >= int(FramesDifferent):
		device.updateStateOnServer("MotionDetected", value="true")
		device.updateStateOnServer("MotionSeconds", value=0)
	
	if int(MotionSeconds) >= int(MotionReset):
		device.updateStateOnServer("MotionDetected", value="false")
	
def GetMosaic(device):
	##################Create tiled version of last 6 images

	SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraName = device.pluginProps["CameraName"]
	CameraDir = CameraDir = MainDir + "/" + CameraName
	MosaicImage = SnapshotDir + "/mosaic.jpg"
	
	sortedList = getSortedDir(CameraDir, "img", 2, 8)
	
	img1 = Image.open(sortedList[0])
	img2 = Image.open(sortedList[1])
	img3 = Image.open(sortedList[2])
	img4 = Image.open(sortedList[3])
	img5 = Image.open(sortedList[4])
	img6 = Image.open(sortedList[5])
	
	#Create mosaic back ground
	mosaic_size = img1.size
	mosaic_size = (mosaic_size[0]*2, (mosaic_size[1]*3))
	mosaic_img = Image.new("RGB", mosaic_size, "white")

	#copy images into mosaic
	mosaic_img.paste(img1, (0,0))
	mosaic_img.paste(img2, (mosaic_size[0]/2,0))
	mosaic_img.paste(img3, (0,mosaic_size[1]/3))
	mosaic_img.paste(img4, (mosaic_size[0]/2,mosaic_size[1]/3))
	mosaic_img.paste(img5, (0,(mosaic_size[1]/3)*2))
	mosaic_img.paste(img6, (mosaic_size[0]/2,(mosaic_size[1]/3)*2))

	#save mosaic
	mosaic_img.save(MosaicImage)


def MasterImage(sub, thread):
	##################Display a master image of different cameras
	
	DeviceID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
	PlayRecording = indigo.activePlugin.pluginPrefs["PlayRecording"]
	RecordingFrame = indigo.activePlugin.pluginPrefs["RecordingFrame"]
	RecordingFlag = indigo.activePlugin.pluginPrefs["RecordingFlag"]  
	MasterCameraDevice = indigo.devices[DeviceID]
	MasterCameraName = MasterCameraDevice.pluginProps["CameraName"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	MasterCameraDir = MainDir + "/" + MasterCameraName
	#MasterRecording = PlayRecording + "/" + RecordingFrame
	MasterRecording = MainDir + "/" + PlayRecording
	MasterImage1 = MainDir + "/Master1.jpg"
	MasterImage2 = MainDir + "/Master2.jpg"
	MasterImage3 = MainDir + "/Master3.jpg"
	
	CurrentImage = MasterCameraDir + "/CurrentImage.jpg"
	
	sortedList = getSortedDir(MasterRecording, "img", 0, 21)
	RecordingImage = sortedList[int(RecordingFrame)]

	if str(RecordingFlag) == "1":
		FileFrom = RecordingImage
	else:
		FileFrom = CurrentImage	
	
	try:
		ChangeFile(FileFrom, MasterImage1)
		ChangeFile(CurrentImage, MasterImage2)
		ChangeFile(RecordingImage, MasterImage3)
	except Exception as errtxt:
		indigo.server.log("Master: " + str(errtxt))

def ChangeFile(FromFile, ToFile):
	##################Change dynamic link
	LinkCommand = "ln -s -f \"" + FromFile + "\" \"" + ToFile + "\""
	proc = subprocess.Popen(LinkCommand, stdout=subprocess.PIPE, shell=True)
	(output, err) = proc.communicate()
	
def RunCarousel(CarouselCamera):
	##################Run Carousel
	
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselOn"]
	CarouselTimer = indigo.activePlugin.pluginPrefs["CarouselTimer"]
	CarouselTimer = int(CarouselTimer) + 1
	
	if int(CarouselTimer) >= 4 and ToggleCarousel == "true":
		CarouselTimer = 0
		CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])
		indigo.activePlugin.pluginPrefs["CarouselCount"] = CarouselCount + 1
		
	indigo.activePlugin.pluginPrefs["CarouselTimer"] = str(CarouselTimer)
	CurrentImage = MainDir + "/" + CarouselCamera + "/CurrentImage.jpg"
	CarouselImage = MainDir + "/CarouselImage.jpg"	
			
	try:
		ChangeFile (CurrentImage, CarouselImage)
	except:
		indigo.server.log("Carousel Image: " + str(CarouselCount))

################################################################################
#
# Start up Procedures
#
################################################################################

class Plugin(indigo.PluginBase):
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.updater = GitHubPluginUpdater(self)

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def startup(self):
		self.debugLog(u"startup called")
		
		indigo.server.log("Checking for update")
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Running the current version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
		
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]

		indigo.activePlugin.pluginPrefs["MasterThreads"] = "0"
		indigo.activePlugin.pluginPrefs["CarouselCount"] = "0"		
		indigo.activePlugin.pluginPrefs["CarouselTimer"] = "0"	
		
		#clear Thread Count
		for sdevice in indigo.devices.iter("self"):
			CameraName = sdevice.pluginProps["CameraName"]
			localPropsCopy = sdevice.pluginProps
			localPropsCopy["ImageThreads"] = "0"
			localPropsCopy["MotionThreads"] = "0"
			sdevice.replacePluginPropsOnServer(localPropsCopy)
		
		#Main dir test
		MainDirTest = os.path.isdir(MainDir)
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)
			
		#Snapshot Test
		SnapshotDirTest = os.path.isdir(SnapshotDir)
		if SnapshotDirTest is False:
			indigo.server.log("Snapshot image directory not found.")
			os.makedirs(SnapshotDir)
			indigo.server.log("Created: " + SnapshotDir)

	def shutdown(self):
		self.debugLog(u"shutdown called")

	def validatePrefsConfigUi(self, valuesDict):
	
		MainDir = valuesDict["MainDirectory"]
		ArchiveDir = MainDir + "/Archive"
		
		#Main Dir Test
		MainDirTest = os.path.isdir(MainDir)		
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)

		#archive dir test
		ArchiveDirTest = os.path.isdir(ArchiveDir)			
		if ArchiveDirTest is False:
			indigo.server.log("Archive image directory not found.")
			os.makedirs(ArchiveDir)
			indigo.server.log("Created: " + ArchiveDir)
		return True

	def didDeviceCommPropertyChange(self, origDev, newDev):
			return False

	def deviceStartComm(self, dev):
		CameraName = dev.pluginProps["CameraName"]
		url = dev.pluginProps["CameraAddress"]		
		dev.stateListOrDisplayStateIdChanged()
	
		localPropsCopy = dev.pluginProps
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
		CameraDir = MainDir + "/" + CameraName
		NotActiveImage = CameraDir + "/NotActive.jpg"
		
		userpwd = url.split("@",1)
		if len(userpwd) > 1:
			user = userpwd[0].split(":")
		
		props = dev.pluginProps
		if not "OriginalAddress" in props:
			props["CameraAddress"] = userpwd[1]
			props["OriginalAddress"] = url
			dev.replacePluginPropsOnServer(props)
		
		if not "uname" in props:
			props["uname"] = user[0]
			dev.replacePluginPropsOnServer(props)
			
		if not "pwd" in props:
			props["pwd"] = user[1]
			dev.replacePluginPropsOnServer(props)

		CameraDirTest = os.path.isdir(CameraDir)
		if CameraDirTest is False:
			indigo.server.log("Camera image directory not found.")
			os.makedirs(CameraDir)
			indigo.server.log("Created: " + CameraDir)
			
		NotActiveImageTest = os.path.isfile(NotActiveImage)
		if NotActiveImageTest is False:
			img = Image.new("RGB", (200, 200), "grey")
			draw = ImageDraw.Draw(img)
			font = ImageFont.truetype("Verdana.ttf", 24)
			center = 100 - ((len(CameraName)*13)/2)
			draw.text((center, 75),CameraName,(255,255,255),font=font)
			center = 100 - ((len("Not Active")*12)/2)
			draw.text((center, 100),"Not Active",(255,255,255),font=font)
			img.save(NotActiveImage)
			indigo.server.log("Created Not Active Image")	
	
		if dev.states["CameraState"] != "Off":
			dev.updateStateOnServer("CameraState", value="On")	
			
		return True

################################################################################
#
# Main looping thread
#
################################################################################

	def runConcurrentThread(self):
		try:
			while True:
				self.sleep(1)

				#Debug Mode
				DebugMode = indigo.activePlugin.pluginPrefs["Debug"]
				self.debug = DebugMode	
				self.debugLog("Starting main loop")
				
				################################################################################
				#
				# Setup
				#
				################################################################################
				
				MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
				RecordingCount = int(indigo.activePlugin.pluginPrefs["RecordingCount"])
				
				#set record loop frame
				if RecordingCount > 20:
					RecordingCount = 0
				else:
					RecordingCount = RecordingCount + 1
					
				RecordingFrame = str(RecordingCount)
				#"00000" + 
				#RecordingFrame = RecordingFrame[-5:] + ".jpg"
				indigo.activePlugin.pluginPrefs["RecordingFrame"] = RecordingFrame
				indigo.activePlugin.pluginPrefs["RecordingCount"] = RecordingCount		
										
				#Create camera device list
				alist = []
				for sdevice in indigo.devices.iter("self"):
					alist.append(sdevice.pluginProps["CameraName"] )
				
				################################################################################
				#
				# Create image carousel
				#
				################################################################################
				self.debugLog("     Starting Carousel")
				CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])
				MaxCarouselCount = len(alist)
				
				if CarouselCount >= MaxCarouselCount-1:
					indigo.activePlugin.pluginPrefs["CarouselCount"] = 0
				
				try:
					CarouselCamera = alist[CarouselCount]
					RunCarousel(CarouselCamera)
				except:
					self.debugLog("     Unable to run Carousel")
				
				################################################################################
				#
				# Set Master Image
				#
				################################################################################
				self.debugLog("     Starting Master Image")
				try:
					MasterID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
					if MasterID != "":
						MasterImage("Master", "Thread")
				except:
					self.debugLog("     Unable to run Master Image")
				
				################################################################################
				#
				# Start device loop
				#
				################################################################################
				
				self.debugLog("     Starting Device Loop")					
				for device in indigo.devices.iter("self"):
					self.debugLog("     Starting Device Loop for:" + device.pluginProps["CameraName"])
					CameraName = device.pluginProps["CameraName"]				
					CameraState = device.states["CameraState"]
					CameraTimeout = int(device.pluginProps["CameraTimeout"])
					MotionThreadSeconds = int(device.pluginProps["MotionThreadSeconds"])
					MotionOff = device.pluginProps["MotionOff"]
					localPropsCopy = device.pluginProps
					CameraDir = CameraDir = MainDir + "/" + CameraName
					NoImage = CameraDir + "/NotActive.jpg"
					CurrentImage = CameraDir + "/CurrentImage.jpg"
					imagedate = time.strftime("%m.%d.%Y.%H.%M.%S")
					NewImage = CameraDir + "/img_" + imagedate + ".jpg"	

					self.debugLog("          Set State Timers")					
					#Set State Timers
					if device.states["RecordSeconds"] > 3600:
						RecordSeconds = 0
						device.updateStateOnServer("RecordSeconds", value=0)
					else:
						RecordSeconds = device.states["RecordSeconds"] + 1
						device.updateStateOnServer("RecordSeconds", value=RecordSeconds)

					self.debugLog("          Get Camera Image")						
					if str(CameraState) != "Off":
						
						#Check for active thread
						ImageThread = False
						for t in threading.enumerate():
							if str(t.getName()) == CameraName:
								ImageThread = True

						#Get Images
						if not ImageThread:
							w = threading.Thread(name=CameraName, target=GetImage, args=(device,))
							w.start()
						else:
							OfflineSeconds = int(device.states["OfflineSeconds"])
							OfflineSeconds += 1
							device.updateStateOnServer("OfflineSeconds", value=str(OfflineSeconds))
						
						OfflineSeconds = int(device.states["OfflineSeconds"])	
							
						if OfflineSeconds >= CameraTimeout:
							device.updateStateOnServer("OfflineSeconds", value="0")
							device.updateStateOnServer("CameraState", value="Unavailable")
							shutil.copy(NoImage, CurrentImage)
							shutil.copy(NoImage, NewImage)

						MotionThread = False
						for t in threading.enumerate():
							if str(t.getName()) == CameraName + "-motion":
								ImageThread = True

						self.debugLog("          Check Motion")						
						#Check Motion
						if str(MotionOff) == "False":
							if not MotionThread:
								w = threading.Thread(name=CameraName + "-motion", target=MotionCheck, args=(device,))
								w.start()
								
		except self.StopThread:
			indigo.server.log("thread stopped")
			pass

################################################################################
#
# Plugin menus
#
################################################################################

	def checkForUpdate(self):
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Running the most recent version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
		
	def updatePlugin(self):
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Already running the most recent version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
			self.updater.update()
    	
################################################################################
#
# Plugin actions
#
################################################################################
	
	def StopCamera(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		indigo.server.log("Stop Camera action called:" + CameraName)
		CameraDevice.updateStateOnServer("CameraState", value="Off")
		
	def StartCamera(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		indigo.server.log("Start Camera action called:" + CameraName)
		CameraDevice.updateStateOnServer("CameraState", value="On")
		CameraDevice.updateStateOnServer("OfflineSeconds", value="On")
		
	def ToggleCamera(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		CameraState = CameraDevice.states["CameraState"]
		localPropsCopy = CameraDevice.pluginProps
		
		if CameraState == "On":
			indigo.server.log("Stop Camera action called:" + CameraName)
			CameraDevice.updateStateOnServer("CameraState", value="Off")
		else:
			indigo.server.log("Start Camera action called:" + CameraName)
			CameraDevice.updateStateOnServer("CameraState", value="On")
			CameraDevice.updateStateOnServer("OfflineSeconds", value="0")
		
	def MasterCamera(self, pluginAction):
		indigo.activePlugin.pluginPrefs["MasterCamera"] = pluginAction.deviceId
		indigo.activePlugin.pluginPrefs["RecordingFlag"] = 0
		MasterImage("Master", "Thread")

	def RecordCamera(self, pluginAction):
		
		time.sleep(2)
	
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		CameraDevice.updateStateOnServer("RecordSeconds", value=0)
		SavedDir = time.strftime("%m %d %Y %H.%M.%S")
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		SourceDir = MainDir + "/" + CameraName
		RecordingDir = MainDir + "/" + CameraName + "/" + SavedDir
		filecounter = 0
		
		os.makedirs(RecordingDir)
		src_files = getSortedDir(SourceDir, "img", 0, 21)
		for file_name in src_files:
			filecounter = filecounter + 1
			try:
				shutil.copy(file_name, RecordingDir)
			except Exception as errtxt:
				self.debugLog(str(errtxt))
		
		sortedList = getSortedDir(SourceDir, "img", 3, 4)
		CurrentImage = sortedList[0]
		
		for num in reversed(range(2, 10)):
			LeadingNum = "0" + str(num)
			Current = LeadingNum[-2:]
			LeadingPrev = "0" + str(num - 1)
			Previous = LeadingPrev[-2:]
			PrevValue = CameraDevice.states["Recording" + Previous]
			CameraDevice.updateStateOnServer("Recording" + Current, value=PrevValue)
			ThumbTo = SourceDir +"/thumb" + Current + ".jpg"
			ThumbFrom = SourceDir +"/thumb" + Previous + ".jpg"
			try:
				os.rename(ThumbFrom, ThumbTo)	
			except Exception as errtxt:
				self.debugLog(str(errtxt))
				
		CurrentThumb = SourceDir + "/Thumb01.jpg"
		shutil.copy (CurrentImage, CurrentThumb)
		CameraDevice.updateStateOnServer("Recording01", value=SavedDir)
		
	def ToggleCarousel(self, pluginAction):
		ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselOn"]
		if ToggleCarousel == "true":
			indigo.activePlugin.pluginPrefs["CarouselOn"] = "false"
		else:
			indigo.activePlugin.pluginPrefs["CarouselOn"] = "true"

	def PlayRecording(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		RecordingID = pluginAction.props["PlaySelect"]
		Recording = CameraName + "/" + CameraDevice.states["Recording" + RecordingID]
		
		indigo.activePlugin.pluginPrefs["RecordingFlag"] = 1
		indigo.activePlugin.pluginPrefs["PlayRecording"] = Recording
		indigo.server.log("Play recording action called:" + CameraName)
		
	def Snapshot(self, pluginAction):
		device = indigo.devices[pluginAction.deviceId]
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		SnapshotImage = SnapshotDir + "/Snap001.jpg"
		
		final_img = GetSnapshot(device)
		
		#save image history
		for num in reversed(range(1, 5)):
			fromfile = "Snap00" + str(num)
			fromfile = SnapshotDir + "/" + fromfile + ".jpg"
			tofile = "Snap00" + str(num+1)
			tofile = SnapshotDir + "/" + tofile + ".jpg"
			if os.path.isfile(fromfile):
				os.rename(fromfile, tofile)	

		try:		
			final_img.save(SnapshotImage)
		except Exception as errtxt:
			self.debugLog(str(errtxt))
		
	def Mosaic(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		GetMosaic(CameraDevice)
		
	def CameraCommand(self, pluginAction):
		ReturnVariable = pluginAction.props["ReturnVariable"]
		CameraCommandURL = pluginAction.props["CameraCommandURL"]
		ReturnVariable = ReturnVariable.replace(" ", "_")
		
		try:
			ReturnVar = indigo.variables[ReturnVariable]
		except Exception as errtxt:
			indigo.server.log(str(errtxt))
			indigo.variable.create(ReturnVariable)
			indigo.server.log(ReturnVariable + " created")
			
		returnvalue = urllib.urlretrieve(CameraCommandURL)
		indigo.variable.updateValue(ReturnVariable, value=str(returnvalue))

		
	def DeleteRecording(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		Months = pluginAction.props["DeleteMonths"]
		Days = int(Months) * 30
		#Days = 4
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		ArchiveDir = MainDir + "/" + "Archive" + "/" + CameraName
		
		OldDirs = []
		today = date.today()
		StartPath = MainDir + "/" + CameraName

		for root, dirs, files in os.walk(StartPath):
			for FileName in dirs:
				filedate = date.fromtimestamp(os.path.getmtime(os.path.join(root, FileName)))
				if (today - filedate).days >= Days:
					CurrentDir =  StartPath + "/" + FileName                                         
					shutil.copytree(CurrentDir,ArchiveDir+ "/" + FileName)
					shutil.rmtree(CurrentDir)
					
		indigo.server.log("Archived videos older than " + Months + " months:" + CameraName)
