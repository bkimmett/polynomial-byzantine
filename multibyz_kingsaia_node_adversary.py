#!/usr/bin/env python

from __future__ import division #utility
import random					#for coin flips
from sys import argv, exit, stdout, exc_info 		#utility
from time import sleep, strftime 	#to wait for messages, and for logging
from math import floor, sqrt, log 			#utility
from copy import deepcopy 		#utility
import numpy as np 				#for matrix operations in _processEpoch
from json import dumps			#for making UIDs good
import traceback 				#debugging
import multibyz_kingsaia_network_adversary as MessageHandler 
#getting an error with the above line? 'pip install kombu'
import collections				#for data type checking of messages
#from enum import Enum			#for reliable broadcast and byzantine message mode phasing
#getting an error with the above line? 'pip install enum34'
from blist import blist 		#containers that offer better performance when they get big. maybe unnecessary?
#getting an error with the above line? 'pip install blist'

#debug logging

debug_rb = False
debug_rb_coin = False
debug_rb_accept = False
debug_byz = True


#Reminder: message[sender] is the node that sent the message the 'last mile'. It is NOT the original sender. rbid[0] is the real originating sender.

#TODO: Modified-Bracha as written down has flaw - Case C branch never taken, coin toss value isn't listened to, which would make this algorithm deterministic (impossible)


#some concerns:
#how to add a node to the thing?
#node has to know WHO to send 'I'm here' messages to.
#once it knows that, it can get the size of the network.


#Basically, the problem arises in that if the new node contacts an adversarial node first, the adversarial node can effectively lock it out of the network. So it has to contact at least 3f+1 nodes. But it doesn't know the size of the network...

#not sure how adding can work WITHOUT eventual synch. Maybe have a client req to add node.

#leaving is a similar issue: how do you know it's not just the adversary sitting on the leaving node?
#unless that node announces they're leaving to everyone. That could work.


#global data structures:
#for EACH ROUND of byzantine agreement
#since many agreement rounds may be being handled at the same time, each needs a unique ID.

#unused for now but should be different for each node
#list_of_nodes = [] #unused now but should specify other nodes. eventually, network should check incoming messages and treat unrecognized nodes differently - perhaps hold them until recognized?
#num_nodes = len(list_of_nodes)
#fault_bound = num_nodes // 3 - 1 if num_nodes % 3 == 0 else num_nodes // 3 #t < n/3. Not <=.

#stores 'echo'/'ready' messages 
#should be pruned a period of time after a message is r-received
#storage format: by key, then a list:
#[initial_received (t/f), echos_received, readys_received, mode]
#wherein 'mode' is 1 (if just sent, or received for the first time), 2 (sent echoes, prepping to send ready), 3 (sent ready, prepping to accept), 4 (accepted, stop processing)


		
username = None
num_nodes = 0
all_nodes = []
fault_bound = 0
message_counter = 0
try:
	random_generator = random.SystemRandom()
except:
	print "Couldn't initialize RNG. Check that your OS/device supports random.SystemRandom()."
	exit()

		
class ReliableBroadcast: # pylint: disable=no-init

	#TODO: There's a little problem with this - basically, it's based on the assumption that there is one list of nodes, which never changes IN SIZE. As the fault bound (t) is a proportion of the number of nodes (n), if those numbers change in the middle of a reliable broadcast instance
	
	# What can be done to fix this: 
	#[1] If a message comes in with a ByzID, it uses the ByzantineAgreement object's node list. Any messages from nodes not on the node list are completely and totally ignored. 
	#[2] If a message comes in without a ByzID, we have to guess. So take getAllNodes() and store that, and use that as the node list, OR just accept from anybody (though using the latter approach is prone to breakage if the node list is updated in the middle. Bracha didn't plan for THIS.)
	#[3] If we broadcast a non-Byz message, we set up the node list based on our knowledge at time of sending [getAllNodes().]
	
	broadcasting_echoes = {}
	
	num_nodes = None
	fault_bound = None
	
	#RBPhase = Enum('RBPhase',['initial','echo','ready','done'])
	class RBPhase: # pylint: disable=no-init,too-few-public-methods
		initial = 1
		echo = 2
		ready = 3
		done = 4
	#a note on these phases: the first three are used to tag individual reliable broadcast messages, BUT ALSO all four are used to indicate what state a node is in for this reliable broadcast instance: "I just sent THIS type of message" (or 'I received this one' in the case of Initial) or "I'm done!"
	
	#timeout protocol: set most recent update time and if that times out without broadcast completing, we junk it.
	
	
	#TODO: if receiving receives a message from a node not currently in the network, it should store that in case of that node joining later (and the join being late).
	#rev: FLEXNODE
	
	@classmethod
	def log(thisClass,message):
		if debug_rb:
			global username
			print "[{}:{}] {}".format(strftime("%H:%M:%S"),username,message)
			stdout.flush() #force write
	
	@classmethod
	def logCoin(thisClass,message):
		if debug_rb_coin:
			global username
			print "[{}:{}] {}".format(strftime("%H:%M:%S"),username,message)
			stdout.flush() #force write
		
	
	@classmethod
	def initial_setup(thisClass,numnodes):
	
		thisClass.num_nodes = numnodes
		thisClass.fault_bound = (thisClass.num_nodes-1) // 3 #n >= 3t+1  - this variable is 't'
	
	@classmethod
	def setupRbroadcastEcho(thisClass,uid):
		
		thisClass.broadcasting_echoes[uid] = [False, set(), set(), thisClass.RBPhase.initial] #no initial received, no echoes received, no readies received, Phase no. 1
		thisClass.log("Setting up broadcast tracking entry for key < {} >.".format(repr(uid)))
	
	#metadata format:
	#every message is either a client message or node (reliable broadcast) message or node (manual) message.
	#client messages can have whatever metadata they damn well please, ignore them for now.
	#node messages metadata: (phase, RBID)
	#phase - indicates whether this is a reliable broadcast message or not. Possible values include:
		## "initial", "echo", "ready" - part of reliable.
		## "direct" - NOT part of reliable.
		## TODO - change these to enums later. ###############
	#RBID - Reliable Broadcast ID. Has the following components:
		## (initiator, init_ctr, (serial, epoch, iter) OR None)
		## initiator = the sending node that started the reliable broadcast. Used to uniquely identify reliable broadcast instances. 
		## init_ctr = counter of message initiation for the sending node. Used to uniquely identify reliable broadcast instances. 
		## (serial, epoch, iter) - used to uniquely identify an instance of Modified-Bracha. 
			### serial = unique serial number of byzantine agreement instance.
			### epoch = epoch# of Modified-Bracha.
			### iter = iter# of Modified-Bracha.
		## You can also put 'None' in this slot if this is a reliable broadcast message unassociated with a Bracha iteration.
	# RBID might be altered or not present in the event of a direct broadcast message. We don't actually use it, so [shrug]
	
	@classmethod
	def broadcast(thisClass,message,extraMeta=None):
		global message_counter
		
		#adversary intervenes and possibly alters value first
		MessageHandler.sendToAdversary(message,{'phase':thisClass.RBPhase.initial,'rbid':(username,message_counter,extraMeta)})
		#MessageHandler.sendAll(message,{'phase':thisClass.RBPhase.initial,'rbid':(username,message_counter,extraMeta)})
		
		thisClass.log("SENDING INITIAL reliable broadcast message for key < {} > to all.".format(repr(message)))
		message_counter += 1
		#We don't need to call setupRbroadcastEcho yet. The first person to receive the 'initial' message will be-- us! And it'll happen then.
		#Also notably, we don't need a node list to broadcast. We just broadcast to EVERYBODY. Nodes will throw out messages that aren't on their list of participants in a byzantine instance.
	
	@classmethod
	def handleRBroadcast(thisClass,message,checkCoinboardMessages=True):
		#when a coinboard message is released from being held, the release function will call handleRBroadcast but set the extra argument to false. This skips having it checked again. Everyone else: don't use this argument for anything.
		
		#new message format = 
		
		#{'body': message.decode(), 'type': message.headers.type, 'sender': message.headers.sender, 'meta': message.headers.meta}
		
		#meta format: {'phase':thisClass.RBPhase.initial,'rbid':(username,message_counter,extraMeta)}
				
		#TODO: Put 'try' blocks in here in case of malformed data (no rbid, no meta, bad meta, etc)			
		
		sender = message['sender'] #error?: malformed data
		data = message['body'] #new data format: data is just the message, and that's it
		phase = message['meta']['phase']
		rbid = message['meta']['rbid'] #RBID doesn't change after it's set by the initial sender.
		
		if phase == thisClass.RBPhase.initial and sender != rbid[0]:
			#We have a forged initial message. Throw.
			thisClass.log("Error: Received forged initial reliable broadcast message from node {}.".format(sender))
			#TODO: maybe blacklist the sender?
			return None
			
		#TODO: Security measure. If an Initial message says (in the UID) it is from sender A, and the sender data says it is from sender B, throw an exception based on security grounds. Maybe dump that message. Effectively, that node is acting maliciously.
		#rev: PASSWALL
		#This is only applicable once we move away from prototype code.
		
		is_byzantine_related = False
		
		try:
			if len(data) > 0:
				if data[0] == MessageMode.coin_flip or data[0] == MessageMode.coin_list or data[0] == MessageMode.coin_ack or data[0] == MessageMode.bracha:
					is_byzantine_related = True #probably true, anyway. Sadly, I'm doing the old C way of comparing to an obscured constant as opposed to a class instance, because the serialization method (JSON) I'm using can't send objects/custom data types. And switching to an upgraded serializer (pickle) would be flagrantly insecure, to where it would be REALLY EASY for an adversary to take over every node at once by sending a malicious broadcast message. Ripperoni.
		except TypeError:
			pass #it's not byzantine
			
		###try:
		if is_byzantine_related and checkCoinboardMessages and (data[0] == MessageMode.coin_flip or data[0] == MessageMode.coin_list):
			if data[0] == MessageMode.coin_list:
				thisClass.logCoin("Received coin list RB message from {}. Phase: {}.".format(rbid[0],phase))
			instance = ByzantineAgreement.getInstance(rbid[2][0]) #rbid[2][0] = extraMeta[0] = byzID
			if not instance.checkCoinboardMessageHolding(message):
				if data[0] == MessageMode.coin_list:
					thisClass.logCoin("Held by checkCoinboardMessageHolding.")
				return None#if held, stop processing for now
			if data[0] == MessageMode.coin_list:
				thisClass.logCoin("Good to go!")		
					
					
				#coinboard message - possibly hold for later!
				#coinboard messages can be held for the following reasons:
				#GENERATE phase: IF j' (orig. sender) is not me AND message i' (flip#) > 1 AND I haven't received (n-t) acknowledgements for the message of (i'-1,j').
					#release held when: we receive enough acknowledgements for any message() in the coinboard not from us.
				#RESOLVE phase:	IF the list of j' has messages on it that I have not received. 
					#release held when: we receive all messages on that list. We might want to have 'check milestones' for the biggest number of remaining messages in a list, though even then lists might cycle on the hold list a few times.
				
				#TODO: As a check uses i' and j' (part of the message body), this means coinboard messages need to be verified before they are accepted. WELL before.
				#but it means coinboard messages can be accepted without verification (because they already have been). Double-edged sword.
				#TODO: Of course, we validate anyway. And we'll do a secondary message hold when coinboard messages are accepted, because we can still get ones from early/late epochs/iterations. 
		###except Exception as err:
			#TODO: What kind of exceptions can be fired here?
		###	print err
		###	raise err
		
		
		
		uid = (dumps(rbid),message['raw']) #for storage in the log
		#print "Making UID {}".format(uid)
	
		try:
			if uid not in thisClass.broadcasting_echoes:
				thisClass.setupRbroadcastEcho(uid) #TODO: A concern is that a spurious entry could be created after [A] a finished entry is removed and a message arrives late, [B] a malformed entry arrives [C] a malicious entry arrives. In the real world, is there a timeout for rbroadcast pruning? (something on the line of a day to a week, something REALLY BIG) How much storage space for rbroadcast info do we HAVE, anyway?
			
				#there's also the concern that if a node shuts down (unexpectedly?) it loses all broadcast info. Could be resolved by just counting that node towards the fault bound OR semipersistently storing broadcast info.
		except TypeError:
			thisClass.log("Error - Invalid UID: {}".format(uid))
			return None		
		
		#by using sets of sender ids, receiving ignores COPIES of messages to avoid adversaries trying to pull a replay attack.
		
		if phase == thisClass.RBPhase.initial:
			thisClass.broadcasting_echoes[uid][0] = True #initial received!!
			thisClass.log("Received INITIAL reliable broadcast message for key < {} > from node {}.".format(repr(uid),sender))
		elif phase == thisClass.RBPhase.echo:
			thisClass.broadcasting_echoes[uid][1].add(sender)
			thisClass.log("Received ECHO reliable broadcast message for key < {} > from node {}.".format(repr(data),sender))
			if thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.initial or thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.echo:
				thisClass.log("Initial/Echo Phase: {}/{} of {} echo messages so far.".format(len(thisClass.broadcasting_echoes[uid][1]), (thisClass.num_nodes + thisClass.fault_bound) / 2, thisClass.num_nodes)) #print how many echoes we need to advance
			else:
				thisClass.log("{} of {} echo messages.".format(len(thisClass.broadcasting_echoes[uid][1]), thisClass.num_nodes)) #just print how many echoes
		elif phase == thisClass.RBPhase.ready:
			thisClass.broadcasting_echoes[uid][2].add(sender)

			thisClass.log("Received READY reliable broadcast message for key < {} > from node {}.".format(repr(data),sender))
			if thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.initial or thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.echo:
				thisClass.log("Initial/Echo Phase: {}/{} of {} ready messages so far.".format(len(thisClass.broadcasting_echoes[uid][2]), thisClass.fault_bound + 1, thisClass.num_nodes)) #print how many readies we need to advance
			elif thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.ready:
				thisClass.log("Ready Phase: {}/{} of {} ready messages so far.".format(len(thisClass.broadcasting_echoes[uid][2]), thisClass.fault_bound*2 + 1, thisClass.num_nodes)) #print how many readies we need to accept
			else: 
				thisClass.log("{} of {} ready messages.".format(len(thisClass.broadcasting_echoes[uid][2]), thisClass.num_nodes)) #print how many readies we got
		else:
			#error!: throw exception? for malformed data
			thisClass.log("Received invalid reliable broadcast message from node {} ({}).".format(sender,phase))
			return None
			
			
		if thisClass.checkRbroadcastEcho(data,rbid,uid): #runs 'check message' until it decides we're done handling any sort of necessary sending	
			return message #original packed message is fastballed back towards the client, as the validate functions the client will pass it on to use packed format
			
		return None
	
	@classmethod
	def checkRbroadcastEcho(thisClass,data,rbid,uid):
		
		#TODO: A concern - (num_nodes + fault_bound) / 2 on a noninteger fault_bound?
		
		#BROADCAST FORMAT:
		#MessageHandler.sendAll(message,{'phase':RBPhase.initial,'rbid':(username,message_counter,extraMeta)})
					
		if thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.initial:
			#waiting to send echo
			if thisClass.broadcasting_echoes[uid][0] or len(thisClass.broadcasting_echoes[uid][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[uid][2]) >= fault_bound + 1: #one initial OR (n+t)/2 echoes OR t+1 readies
				#ECHO!
				thisClass.log("SENDING ECHO reliable broadcast message for key < {} > to all.".format(repr(data)))
				MessageHandler.sendAll(data,{'phase':thisClass.RBPhase.echo,'rbid':rbid})
				#MessageHandler.sendAll(("rBroadcast","echo",data,None)) 
				#4th item in message is debug info
				thisClass.broadcasting_echoes[uid][3] = thisClass.RBPhase.echo #update node phase
			else:
				return False #have to wait for more messages
				
		if thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.echo:
			#waiting to send ready
			if len(thisClass.broadcasting_echoes[uid][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[uid][2]) >= fault_bound + 1: #(n+t)/2 echoes OR t+1 readies
				#READY!
				thisClass.log("SENDING READY reliable broadcast message for key < {} > to all.".format(repr(data)))
				MessageHandler.sendAll(data,{'phase':thisClass.RBPhase.ready,'rbid':rbid})
				#MessageHandler.sendAll(("rBroadcast","ready",data,None)) #message format: type, [phase, data, debuginfo]
				thisClass.broadcasting_echoes[uid][3] = thisClass.RBPhase.ready #update node phase
			else:
				return False #have to wait for more messages
				
		if thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.ready:
			#waiting to accept
			if len(thisClass.broadcasting_echoes[uid][2]) >= thisClass.fault_bound*2 + 1: #2t+1 readies only
				#ACCEPT!
				thisClass.broadcasting_echoes[uid][3] = thisClass.RBPhase.done
				return thisClass.acceptRbroadcast(data,rbid)
			#otherwise...
			#print "Not accepting, {} of {} messages.".format(thisClass.broadcasting_echoes[uid][2],thisClass.fault_bound*2+1)
			return False #wait for more messages!
		
		if thisClass.broadcasting_echoes[uid][3] == thisClass.RBPhase.done:
			return False #we've already accepted this. no further processing.
		else:
			pass #error! throw exception for malformed data in here. How'd THIS happen?			

	
	@classmethod
	def acceptRbroadcast(thisClass,data,rbid):	# pylint: disable=unused-argument
		return True #data,rbid
		#what does accepting a r-broadcasted message LOOK like? Well, the message is confirmed to be broadcast, and is passed on to the other parts of the program.
		
		#what in Byzantine uses RB:
		
		#what in Byzantine doesn't:

#MessageMode = Enum('MessageMode',['bracha','coin_flip','coin_ack','coin_list'])
class MessageMode: # pylint: disable=no-init,too-few-public-methods
	bracha = 'MessageMode_bracha-0'
	coin_flip = 'MessageMode_coin_flip-1'
	coin_ack = 'MessageMode_coin_ack-2'
	coin_list = 'MessageMode_coin_list-3'
		

class ByzantineAgreement:


	__byzantine_list__ = {}
	
	
	def log(self,message):
		if debug_byz:
			global username
			print "[{}:{}:{}] {}".format(strftime("%H:%M:%S"),username,self.ID,message)
			stdout.flush() #force write
	
	@classmethod
	def getInstance(thisClass,byzID):
		try:
			return thisClass.__byzantine_list__[byzID]
		except (IndexError, TypeError, KeyError):
			if debug_byz:
				print "Tried to get a bad byzantine instance: {}".format(byzID)
			return None #just in case an invalid ID is passed in
		
	#@classmethod
	def setInstance(self):
		self.__byzantine_list__[self.ID] = self
		
		
	#TODO: Add a method for list removal later.
	#TODO: This should be combined with the decision mechanic; it broadcasts its Decision and removes itself from the list? Maybe?

	def __init__(self,byzID,byzValue,epochConst=1,iterConst=2):
		self.ID = byzID
		self.log("Starting new Byzantine instance. {}".format(byzValue))
		#FUTURE: Split what happens next by if the Value is True/False (a single-valued byzantine) or something else (a multi-valued byzantine).
		self.value = (byzValue,) #a tuple! (The second value is used for 'deciding' later.)
		self.origValue = (byzValue,)
		#ASSUMPTION: For now, value should be True or False: a single-valued byzantine thing.
		
		
		self.heldMessages = {'epoch':{}, 'iteration':{}, 'wave':{2:[[],[]], 3:[[],[]]}, 'coin_epoch':{}, 'coin_epoch_accepted':{}, 'coin_iteration':{}, 'coin_iteration_accepted':{}, 'coin_flip':{}, 'coin_list':[]}
		#held wave 3 messages are deciding messages.
		
		self.decided = False
		self.decision = None
		self.useCoinValue = False
		self.resets = -1
		
		self.nodes = blist(getAllNodes()) #expecting a tuple of node IDs to be returned. This is never edited after.
		
		self.num_nodes = len(self.nodes)
		self.fault_bound = floor((self.num_nodes-1)/3) #n >= 3t+1  - this variable is 't'
		self.coin_fault_bound = self.fault_bound #TODO - coin fault bound is going to be smaller than byzantine fault bound... maybe?
		self.initial_validation_bound = (self.num_nodes - self.fault_bound) // 2 + 1 # (n - t) / 2 + 1. Used to validate wave 2 bracha messages. Never changes even as nodes are blacklisted from our end, because we can't assume the size of other nodes' blacklists because: 
		#the condition for validating a wave 2 message is that the node that sent the message had to have received some combination of wave 1 messages that could have made it send a wave 2 message.
		#which in this case is they received n - t messages, and over half that many (a majority) were for the set value. So we just need (n - t) // 2 + 1 messages to be in the chosen value.
		#this happens to be about equal to t+1 messages, with t at worst case.
		
		self.maxIterations = iterConst * len(self.nodes)
		self.maxEpochs = epochConst * len(self.nodes) 
		
		self.corrupted = False
		self.bracha_gameplan = None
		self.coin_gameplan = None
		
		self._reset() #sets up rewindable parts of agreement attempt.
		
		self.setInstance() #TODO: Yeah, is this gonna work?
		
		self._startEpoch()
		
		
	
	def _reset(self):
		if self.decided: #inactive after decision
			return 
		self.log("Resetting Byzantine instance.")
		self.value = deepcopy(self.origValue) #reset value to start.
		#TODO: Does reset() need to reset the node's initial value? This code assumes 'yes'. Otherwise, delete the above line.
		self.goodNodes = blist(self.nodes) #reset blacklist
		self.badNodes = [] #we need this to validate messages from other nodes 
		self.scores = [0 for _ in self.nodes] #reset list of scores
		
		self.pastCoinboards = {}
		self.pastCoinboardLogs = {} #log the past coinboard as we recorded it then any updates - two copies. One for as it was when we recorded it in logs, one for any updates after being shelved.
		
		#self.pastWhitelistedCoinboardLists = {} #dictionary of sets - do we need this?
		
		#past coinboards are stored by a tuple of (epoch,iteration).
		
		#a few notes on how the byzantine algorithm works and using fake multithreading
		#(aka 'event-driven programming')...
		#Start Epoch starts Bracha.
		#Bracha broadcasts the first wave and RETURNS until enough Wave 1 messages are validated.
		#then we set the byzValue and broadcast the second wave... yeah.
		#receiving bracha broadcast messages acts as a handler. 
		#this handler will trigger bracha next wave if necessary.
		
		self.resets += 1
		
		self.epoch = self.maxEpochs * self.resets #epoch = 0 to maxEpochs-1. If a reset occurs, we start at maxEpochs+0, +1, +2, etc.
	
	def _startEpoch(self):
		if self.decided: #inactive after decision
			return 	
		
		self.log("Starting epoch {} for byzantine instance.".format(self.epoch))
		
		if self.epoch >= self.maxEpochs * (self.resets+1):
			self._reset()
			
		
			
		##### VERY IMPORTANT TODO: We are assuming that there are exactly n iterations in an epoch. The original paper has m = Big-Theta(n) as the limit instead, and later on suggests m >= n for statistical analysis to work. What's the REAL max value of M?
		self.iteration = 0
		self.clearHeldIterMessages()
		
		self.coinboardLogs = {}
		
		self.epochFlips = []
		
		#TODO: What else gets cleared on new epoch?
		
		self._startBracha()
		
	def _startBracha(self):
		if self.decided: #inactive after decision
			return 
			
		self.log("Starting iteration {} of epoch {}.".format(self.iteration,self.epoch))
			
		if self.iteration >= self.maxIterations: #nvm, start a new EPOCH instead
			#TODO: call process epoch
			self._processEpoch()
			self.epoch += 1
			self._startEpoch()
			return	
		#starts an iteration.
		
		#include all coinboard reset stuff.
		self.coinboard = [] #erase coin records - coinboard will have been stored in self.pastCoinboards by _finalizeCoinboard
		self.coinState = 0 
		self.coinColumnsReady = 0 #how many columns have been received by at least n-t nodes?
		self.precessCoin = False #if we're in coinState 0, do we move to coinState 2 immediately after coinState 1?
		self.precessCoinII = False #do we move to coinState 3 immediately after coinState 2?
		self.lastCoinBroadcast = 0 #what's the last message_i (of our own) we broadcast?

		self.coinState = 0 
		#0 = coinboard not yet running
		#1 = coinboard running in 'generate' phase
		#2 = coinboard running in 'reconcile' phase
		#3 = coinboard is over

		
		#COINBOARD FORMAT:
		#array of x dicts. (where x is as in x-sync - number of rounds.) Dict #i  is for round i.
		#in each dict, keys are the j' s (usernames of nodes).
		#each value is a tuple: (value, acks)
		#where acks is a set() of who acks have been received from for this message.
		
		
		
		self.brachabits = {node: [True, None, None, None] for node in self.goodNodes}
		self.brachabits.update({node: [False, None, None, None] for node in self.badNodes})
		#above is message storage for validation purposes
		#add a slot for each good node (first dict) and append slots for bad nodes to it (the .update part).
		#potential perils: if somehow a bad node and a good node have the same identifier (which SHOULD be addressed and filtered for elsewhere), the entry for the bad node will overwrite that of the good one.
		#but that presupposes a breakdown of some sort earlier, as node names REALLY SHOULD be unique.
		self.brachaMsgCtrGood = [[0,0],[0,0],[0,0]]
		self.brachaMsgCtrTotal = [[0,0],[0,0],[0,0]]
		self.brachaMsgCtrGoodDeciding = [0,0]
		#these are counters. They count the total number of verified messages with their value of False [0] and True [0], for each of waves 1, 2, 3.
		#the third counter counts only the verified messages from good nodes that have indicated they are ready to decide.
	
		
		self.whitelistedCoinboardList = set()
		self.knownCoinboardList = set()
		#these keep track of which coinboards we've received in this epoch/iteration pair. 
		
		
		if self.corrupted and self.bracha_gameplan is not None and self.bracha_gameplan[0] is not None:
			self.value = (self.bracha_gameplan[0],) #pawn of the adversary says what?
		
		
		#aka Bracha Wave 1
		if not self.corrupted or self.bracha_gameplan is not None: #if the entire gameplan is none, don't broadcast at all.
			ReliableBroadcast.broadcast((MessageMode.bracha, 1, self.value),extraMeta=(self.ID,self.epoch,self.iteration))
		#also, count myself (free).
		self.brachabits[username][1] = self.value[0]
		#if self.brachabits[username][0]: #if we're a good node:
		self.brachaMsgCtrGood[0][1 if self.value[0] else 0] += 1 ###we're always a good node
		self.brachaMsgCtrTotal[0][1 if self.value[0] else 0] += 1
		
		#after we send our own message, we might as well check to see if there's any messages waiting.
		if self.iteration == 1:
			self.checkHeldEpochMessages(self.epoch)
			self.checkHeldCoinEpochMessages(self.epoch)
		else:
			self.checkHeldIterMessages(self.iteration)
			self.checkHeldCoinIterMessages(self.iteration)
		self.wave = 1
		self.clearHeldWaveMessages()
		self.clearHeldCoinListMessages()
		
		
	def validateBrachaMsg(self,message):		
		if self.decided: #inactive after decision
			return 
			
		try: 
			rbid = message['meta']['rbid']
		except (IndexError, TypeError):
			self.log("Couldn't validate bracha message with bad RBID.")
			return
			
		#PERPETUAL TODO: Better validation of bracha-style messages.
		try:
			extraMeta = rbid[2]
			remoteByzID = extraMeta[0]
			if self.ID != remoteByzID:
				self.log("Throwing out bracha message from {} with wrong Byzantine ID {} vs {}.".format(rbid[0],remoteByzID,self.ID))
				self.log("You should probably check your message routing. This isn't supposed to happen.")
				return #throw out message. Somehow it was sent to the wrong byzantine agreement object entirely. How did this even happen?
			
			##Check Epoch
			epoch = int(extraMeta[1])
			if epoch < self.epoch:
				self.log("Throwing out old bracha message from {}, epoch {} vs {}.".format(rbid[0],epoch,self.epoch))
				return #throw out message - it's old and can't be used
			if epoch > self.epoch:
				self.log("Holding too-new bracha message from {}, epoch {} vs {}.".format(rbid[0],epoch,self.epoch))
				self.holdForLaterEpoch(message,epoch)
				return #this message can't be processed yet, it's from a different epoch entirely
			
			##Check Iteration
			iteration = int(extraMeta[2])
			if iteration > self.maxIterations:
				#a note about this part: one of the flaws in byzantine agreement is it assumes EVERY NODE KNOWS HOW MANY NODES THERE ARE AND WHO THEY ARE. If you're gonna add nodes to the network in real time you're probably going to have to do it BY byzantine agreement or a trusted third party, and then it'll take some nontrivial management to make sure enough nodes' node lists stay synchronized.
				#one thing this code DOES NOT ACCOUNT FOR is how to handle the effects of nodes joining and leaving in a resilient manner. As the classic textbook line goes, this is "left to the reader as an exercise". Sorry!
				#the reason I'm mentioning this here is that one of the reasons the below scenario can take place is that some nodes got the memo about a new node joining when this agreement instance started - and some (this one!) didn't.
				self.log("Throwing out impossible bracha message from {}, iteration {} (max {}).".format(rbid[0],iteration,self.maxIterations))
				self.log("This can indicate a fault or nodes that are not uniformly configured with a maximum iteration limit (or nodes that have a different node list than this node at the start of the byzantine bit).")
				return #this can't be processed, it's from an iteration that's not supposed to happen.
			if iteration > self.iteration:
				self.log("Holding too-new bracha message from {}, iteration {} vs {}.".format(rbid[0],iteration,self.iteration))
				self.holdForLaterIteration(message,iteration)
				return #this message can't be processed yet, maybe next (or some later) iteration
			if iteration < self.iteration:
				self.log("Throwing out old bracha message from {}, iteration {} vs {}.".format(rbid[0],iteration,self.iteration))
				return #this message is from a past iteration that already concluded and is thus stale.
			
			##Check Wave
			wave = int(message['body'][1])
			if wave != 1 and wave != 2 and wave != 3:
				self.log("Throwing out impossible bracha message from {} via {}, invalid wave {}.".format(rbid[0],message['sender'],wave))
				return #wave can only be one, two, or three. period.
			
			msgValue = message['body'][2]
			if not isinstance(msgValue, (tuple,list)) or (len(msgValue) not in [1,2]) or not all(type(item) is bool for item in msgValue):
				#must be a tuple of 1 or 2 items. First item is value. Second item is wave 3 'decide' flag. Decide flag is ignored if it's a wave1/wave2 message.
				#TODO - double check. Is everything supposed to be a boolean in this?
				self.log("Throwing out impossible bracha message from {} via {}, invalid message type {}.".format(rbid[0],message['sender'],type(msgValue)))
				self.log("Message was {}".format(msgValue))
				return
			
		except (TypeError, ValueError, IndexError):
			self.log("Value error. Message from {} via {} had to be discarded.".format(rbid[0],message['sender']))
			return 
			
		#unpack msgValue	
		if wave == 3:
			msgDecide = msgValue[1]
		msgValue = msgValue[0] #strip 'decide' flag
		
		
		#validating time! 
		
		if wave == 1 or self.corrupted:
			#wave 1 messages are always valid. #if we are corrupted by the adversary, skip validation.
			pass
		elif wave == 2:
			if self.brachaMsgCtrTotal[0][1 if msgValue else 0] < self.initial_validation_bound:
				#message isn't valid - we haven't received enough appropriate wave 1 messages.
				#we hold the message if there is the *potential* for there to be enough wave 1 messages. Otherwise we throw it out.
				if self.num_nodes - sum(self.brachaMsgCtrTotal[0]) + self.brachaMsgCtrTotal[0][1 if msgValue else 0] >= self.initial_validation_bound:
					#...but we COULD hit it later.
					self.log("Holding uncertain wave 2 bracha message from {}, might not have enough wave 1 messages to validate {}.".format(rbid[0],msgValue))
					self.holdForLaterWave(message, 2, msgValue) #needs self.initial_validation_bound messages of same type to release
						#self.initial_validation_bound - self.brachaMsgCtrTotal[0][1 if msgValue else 0])
					return
				else:
					#...and we're not going to be able to hit it in this go-round.
					self.log("Discarding unvalidateable wave 2 bracha message from {}, not enough wave 1 messages to validate {}.".format(rbid[0],msgValue))
					return
				
				
			#wave 2 messages are valid IF we received at least n - t wave 1 messages (from any nodes) AND a majority of those n - t is for the value listed in the wave 2 message.
			#this is complicated somewhat by the fact that n - t >= 2t + 1. So the number of values we need for a 'majority' is actually (n - t) // 2 + 1. Or, about t+1. So it's possible for enough wave 1 messages to come in that wave 2 messages taking either position are viable.
		elif wave == 3:
			#wave 3 messages are more straightforward to validate - more than half of the nodes have to have settled to a pattern. This is quite unequivocal. 
			if not msgDecide:
				if self.brachabits[rbid[0]][2] == None: #previous message wasn't read at all
					self.log("Holding uncertain non-deciding wave 3 bracha message from {}, waiting for the associated wave 2 message.".format(rbid[0],msgValue))
					self.holdForLaterWaveSpecial(message,rbid[0])
					return
			
				if msgValue != self.brachabits[rbid[0]][2] or self.brachaMsgCtrTotal[1][1 if msgValue else 0] >= self.num_nodes // 2 + self.fault_bound + 1:
					#basically, if 'decide' is false, two things must be true:
					#1. The node must have the same value as its Wave 2 message.
					#2A. There must not be more than n//2 + t nodes that have a specific value in their wave 2 message, as if there were, such a hypermajority would force the node to set 'decide' to true and their value to that value.
					#2B. This second condition is hard to hit as it requires this node receive more than n - t messages, but I'm including it just in case as it is a condition to check for.
					self.log("Discarding unvalidateable wave 3 bracha message from {}, sender is not deciding and {} {}.".format(rbid[0], "changed value to" if msgValue != self.brachabits[rbid[0]][2] else "would be forced to decide", msgValue))
					#TODO: Maybe blacklist here?
					return
			
			if msgDecide and self.brachaMsgCtrTotal[1][1 if msgValue else 0] <= self.num_nodes // 2:
				#message isn't valid - we haven't received enough appropriate wave 2 messages.
				#we hold the message if there is the *potential* for there to be enough wave 1 messages. Otherwise we throw it out.
				if self.num_nodes - sum(self.brachaMsgCtrTotal[1]) + self.brachaMsgCtrTotal[1][1 if msgValue else 0] > self.num_nodes // 2:
					#...but we COULD hit it later.
					self.log("Holding uncertain wave 3 bracha message from {}, might not have enough wave 2 messages to validate {}.".format(rbid[0],msgValue))
					self.holdForLaterWave(message, 3, msgValue) #(self.num_nodes // 2 + 1) - self.brachaMsgCtrTotal[1][1 if msgValue else 0]) #second number is minimum number of messages needed before recheck 
					return
				else:
					#...and we're not going to be able to hit it in this go-round.
					self.log("Discarding unvalidateable wave 3 bracha message from {}, not enough wave 2 messages to validate {}.".format(rbid[0],msgValue))
					return
		
		
		
			
		#now check that we can actually store the messages	
		
		#TODO: Switch check vs self.nodes to up here instead of relying on a try. Keep the try anyway.
		
		try:
			if not self.corrupted and self.brachabits[rbid[0]][wave] is not None:
				if msgValue != self.brachabits[rbid[0]][wave]:
					#wut-oh. In this case, there was a mismatch between a previous message we received and a current message - in the same wave. As in, that was already sent. This is indicative of a faulty node and earns the node a spot on the blackList.
					self.log("Received the same message with different values from node {}. This smells! Blacklisting.".format(rbid[0]))
					self.log("Expected {} of type {}, got {} of type {}".format(self.brachabits[rbid[0]][wave], type(self.brachabits[rbid[0]][wave]), msgValue, type(msgValue)))
					self.blacklistNode(rbid[0]) #remember, a reliable broadcast sender (rbid[0]) can't be forged because it has to match the initial sender of the message, and THAT can't be forged. This property has to hold for this to work.
						
							
				#you'll note there's the end of this if block. If there's a duplicate message, we do nothing; we recorded it already.	
			else:
				if self.corrupted and self.brachabits[rbid[0]][wave] is not None:
					#corrupted - unwind current received record so we can replace it with the incoming message
					msgOldValue = self.brachabits[rbid[0]][wave]
					self.brachaMsgCtrGood[wave-1][1 if msgOldValue else 0] -= 1
					if wave == 3 and msgDecide: #if they're deciding, record it as a deciding message
						self.brachaMsgCtrGoodDeciding[1 if msgOldValue else 0] -= 1
		
					self.brachaMsgCtrTotal[wave-1][1 if msgOldValue else 0] -= 1 	
			
				self.brachabits[rbid[0]][wave] = msgValue
				#TODO: 'Good' was originally only supposed to apply to Global-Coin, not bracha. Are we supposed to count separately here?
				#if self.brachabits[rbid[0]][0]: #that is, if the node is deemed Good
				###BRACHA NOTE: Remove the above line and de-indent the below block to prevent blacklisting applying to bracha.
				self.brachaMsgCtrGood[wave-1][1 if msgValue else 0] += 1
				if wave == 3 and msgDecide: #if they're deciding, record it as a deciding message
					self.brachaMsgCtrGoodDeciding[1 if msgValue else 0] += 1
				###END OF ABOVE BLOCK		
		
				self.brachaMsgCtrTotal[wave-1][1 if msgValue else 0] += 1 
				
				self.log("Successfully received {}wave {} bracha message (val: {}) from {}. Count {}:{}".format('deciding ' if (wave == 3 and msgDecide) else '', wave,msgValue,rbid[0],wave,self.brachaMsgCtrGood[wave-1][::-1]))	
				
				if self.wave == 1 and sum(self.brachaMsgCtrGood[0]) >= self.num_nodes - self.fault_bound:
					self.wave = 2
					self._brachaWaveTwo()
					
				if self.wave == 2:
					if sum(self.brachaMsgCtrGood[1]) >= self.num_nodes - self.fault_bound:
						self.wave = 3
						self._brachaWaveThree()	
					
				if self.wave == 3:
					if sum(self.brachaMsgCtrGood[2]) >= self.num_nodes - self.fault_bound:
						self.log("Done with Bracha. Result due shortly...")
						self.wave = 4 #done with waves - mostly acts to prevent this from firing again
						self._brachaFinal()
				
				if wave == 1: #note that 'wave' in this case is the wave of the MESSAGE, not US
					self.checkHeldWaveMessages(2)
					#check wave messages if we got a wave 1 message, which might release held wave 2 messages
					
				if wave	== 2:
					self.checkHeldWaveMessagesSpecial(rbid[0]) #we validated a wave 2 message, so make sure the wave 3 message didn't just happen to be waiting the whole time
					self.checkHeldWaveMessages(3)
					#check wave messages - happens after potential wave update to ensure quasi-atomicity
				
				#increment counters 
				#Release held stage 2 or 3 messages if we have enough stage 1/2 messages.
				#Call stage 2 or 3 if warranted.
					
		except KeyError:
			self.log("Received a bracha message from a node I've never heard of: {} via {}.".format(rbid[0], message['sender']))
			#traceback.print_exc(None,stdout)
			#IMPORTANT: so we have a specific defined behavior here: **We throw out the message.** This IS the flexible-node-list resilient behavior. Why? Because the node list is set at the start of the node opening the byzantine instance. If a new node is added to the global roster, it can jump in on new byzantine instances but not ones that are already in progress!
			return 
		
		
	def validateCoinMsg(self,message):
		#we still accept coinboard messages after decision... right?
		
		try: 
			rbid = message['meta']['rbid']
		except (IndexError, TypeError):
			self.log("Couldn't validate coinboard message with bad RBID.")
			return
		
		try: 
			#this first bit is just about the same as bracha: epoch and iteration-
			#-except we don't throw out old coin messages. We process them like all others.		
			#this variable determines whether it's an old coin message or not.
			message_from_the_past = False
			extraMeta = rbid[2]
			
			##Check Epoch
			epoch = int(extraMeta[1])
			if epoch < self.epoch:
				message_from_the_past = True
			if epoch > self.epoch:
				self.log("Holding too-new coin message from {}, epoch {} vs {}.".format(rbid[0],epoch,self.epoch))
				self.holdAcceptedCoinForLaterEpoch(message,epoch)
				return #this message can't be processed yet, it's from a different epoch entirely
			
			##Check Iteration
			iteration = int(extraMeta[2])
			if iteration > self.maxIterations:
				
				self.log("Throwing out impossible coin message from {}, iteration {} (max {}).".format(rbid[0], iteration, self.maxIterations))
				self.log("This can indicate a fault or nodes that are not uniformly configured with a maximum iteration limit (or nodes that have a different node list than this node at the start of the byzantine bit).")
				return #this can't be processed, it's from an iteration that's not supposed to happen.
			if iteration > self.iteration:
				self.log("Holding too-new coin message from {}, iteration {} vs {}.".format(rbid[0],iteration,self.iteration))
				self.holdAcceptedCoinForLaterIteration(message,iteration)
				return #this message can't be processed yet, maybe next (or some later) iteration
			if iteration < self.iteration:
				message_from_the_past = True
			
			## Check data integrity
			data = message['body']
			mode = data[0]
			
			if mode != MessageMode.coin_flip and mode != MessageMode.coin_ack and mode != MessageMode.coin_list:
				self.log("Throwing out not-a-coin message from {} via {} (real type {}).".format(rbid[0],message['sender'],type(mode)))
				self.log("This is NOT supposed to happen - noncoin messages aren't even supposed to hit this function. Debug time!")
				return #this can't be processed, no way no how.
					
		except Exception as err:
			print err 
			raise err
			#TODO: build a better exception handler and handle errors properly
			
		if rbid[0] not in self.nodes or message['sender'] not in self.nodes:
			self.log("Who sent this? Received a coin message from/via a node {} via {} we don't know.".format(rbid[0], message['sender']))
			return
		
		##Check Type
			#if it's a flip message it got through the pre-checks and so is valid to be processed. So we tag it and (if our state is still running the board) send an acknowledgement by broadcast.
			#if it's an acknowledgement we accept it and do a Hold Release for flips if necessary.
			#if it's a coin list, well, it depends on our state, again.
			
		#message format expected:
		#flip: i, j, value
		#ack: i, j
		#list: [list]	
			
		if mode == MessageMode.coin_flip or mode == MessageMode.coin_ack:
			try:
				message_i = data[1]
				message_j = data[2]
				if mode == MessageMode.coin_flip:
					message_value = data[3]
			except (IndexError,TypeError,KeyError):
				self.log("Discarding completely invalid coinflip message from {} via {}, missing some data.".format(rbid[0],message['sender']))
				return			
		
			if type(message_i) is not int:
				self.log("Invalid coinflip message from {} via {}, sync round# type {} instead of integer.".format(rbid[0], message['sender'], type(message_i)))
				return
		
			if message_i < 0 or message_i >= self.num_nodes: ###is this the right message_i max?
				self.log("Invalid coinflip message from {} via {}, impossible round# {}.".format(rbid[0], message['sender'],message_i))
				return
		
			if message_j not in self.nodes:
				#By the way: there's probably a line to be had here about untrusted data, but we're assuming adversaries WILL NOT try to induce arbitrary code execution with node IDs, or anything else. 
				#if you are reading this, and you're implementing this on a production system, you had better sanitize your inputs and add whatever else security you think is necessary, 'k? I did my best, but there's no WAY I thought of everything.
				self.log("Received a coin message about a node {} we don't know.".format(message_j))
				return
		
			if mode == MessageMode.coin_flip and type(message_value) is not bool:
				self.log("Invalid coinflip message from {} via {}, message type {} instead of boolean.".format(rbid[0], message['sender'], type(message_value)))
				return

			if message_from_the_past:
				if (epoch,iteration) not in self.pastCoinboards:
					#we don't have ANY coinboard records from back then. How'd that happen? 
					self.log("Warning: had to generate a new past coinboard for old epoch/iter {}/{}.".format(epoch,iteration))
					#generate a new coinboard on the spot.
					self.pastCoinboards[(epoch,iteration)] = [{} for _ in range(self.num_nodes)]
					
				this_coinboard = self.pastCoinboards[(epoch,iteration)]
			else:
				this_coinboard = self.coinboard
			
			if not self.ensureCoinboardPosExists(this_coinboard, message_i, message_j):
				self.log("Couldn't accept {}'s coin flip message - impossible round (i) number: {}.".format(rbid[0],message_i))
				return
			
			#replaced with ensureCoinboardPosExists	
			#while len(this_coinboard) <= message_i:
			#	this_coinboard.append({}) #add blank extra spaces to fill out board
			#if message_j not in this_coinboard[message_i]:
			#	this_coinboard[message_i][message_j] = [None,set()] #setup record
			
			##OK, we've done some light validation, now store it.
			
			if mode == MessageMode.coin_flip:
				if message_j != rbid[0]: #sender doesn't match who the message is about, i.e. this is a forgery or a screw-up of grand proportions
					self.log("{} tried to forge {}'s coin flip message. Discarding/blacklisting.".format(rbid[0],message_j))
					self.blacklistNode(rbid[0])
					return
			
				if this_coinboard[message_i][message_j][0] is None:
					#no value stored
					this_coinboard[message_i][message_j][0] = message_value
					
					if message_from_the_past:
						self.log("Received historic coin flip #{} from {}, value {}. (e:{} i:{})".format(message_i, message_j, message_value, epoch, iteration))
						self.logPastCoinFlip(message_value,message_j,iteration, epoch)
					else:
						self.log("Received coin flip #{} from {}, value {}.".format(message_i, message_j, message_value))
						self.logCoinFlip(message_value,message_j,iteration) #message_i (round#) doesn't matter for logs
						self.checkHeldCoinListMessages(message_i,message_j)
						#check coin list messages here.
					#TODO: When we start a new iteration, clear out held coin list messages.
					
					if not message_from_the_past and self.coinState < 2:
						self._acknowledgeCoin(message_i,message_j)
						#Broadcast acknowledgement that we received this message - but only if this is the current coinboard and we haven't sent our own list yet.
						
				else:
					if message_value != this_coinboard[message_i][message_j][0]:
						#We have two messages with different values? This isn't supposed to happen. Blacklist the node...
						self.log("{} sent the same flip twice, with two different values. Discarding/blacklisting.".format(rbid[0]))
						self.blacklistNode(rbid[0])
					else:
						self.log("Received duplicate coin flip #{} from {}, value {}.".format(message_i, message_j, message_value))
					#either way, if it's a copy with the same value, we just throw it out - duplicate. 	
					return
						
			
			if mode == MessageMode.coin_ack:
				if rbid[0] in this_coinboard[message_i][message_j][1]:
					self.log("Received duplicate acknowledgement from {} for coin flip #{} of node {}. (Sender: {})".format(rbid[0], message_i, message_j,message['sender']))
					#duplicates CAN happen! This prevents any shenanigans from going on.
					return
				
				this_coinboard[message_i][message_j][1].add(rbid[0]) #sender of broadcast
				self.log("Received acknowledgement from {} for coin flip #{} of node {}. (Sender: {})".format(rbid[0], message_i, message_j,message['sender']))
				#Check number of acknowledgements.
				if len(this_coinboard[message_i][message_j][1]) == self.num_nodes-self.fault_bound:
					self.log("Got enough acknowledgements for coin flip #{} of node {}.".format(message_i, message_j))
					#we've hit the boundary number of acknowledgements! (n-t)
					#we trigger this only once - it does things like continue the state.				
					#we also (if we're in Stage 1) need to check for the number of acknowledgements - if we get enough columns, we move on to stage 2. (If we're in Stage 0, we store that we're ready to move on until Stage 1...)
					if not message_from_the_past and self.coinState < 2:
						if message_i == self.num_nodes-1: #coinboard maxed out? 
							self.log("Column of coin flips complete for node {}.".format(message_j))
							self.coinColumnsReady += 1
							if self.coinColumnsReady == self.num_nodes - self.fault_bound:
								self.log("We have enough columns to move to the next stage.")
								if self.coinState == 1:
									self.log("Moving to coinboard stage 2 (list).")
									self.coinState = 2
									self._broadcastCoinList()
									if self.precessCoinII:
										self.log("Precessing to coinboard stage 3 (complete).")
										self.coinState = 3
										self._finalizeCoinboard() 
								else:
									self.log("Precess 1 is set; coinboard will go straight to stage 2 (list) when started.")
									self.precessCoin = True
								#move to state 2... or at least say we're ready to do so	
					
					if message_j == username:
						#if we reach the set number for our flip, broadcast the next flip.
						if not message_from_the_past:	
							#this does assume it's OUR flip NOW, mind you. If we've gotten all the acknowledgements finally for an old coinboard, then the decision is already made and there's no point updating it further.				
							if message_i != self.lastCoinBroadcast:
								self.log("SERIOUS ERROR: OK, so we just received the correct number of acknowledgements for one of our {} coin flips, and not the one we just broadcast (currently {} vs {} received). This SHOULD be completely impossible without time travel, glitch, or forgery on a grand scale. ".format("earlier" if message_i < self.lastCoinBroadcast else "later", self.lastCoinBroadcast, message_i))
								#TODO: But do we DO anything about it?
							else:
								self.log("Got enough acknowledgements for our own coin flip #{}.".format(message_i))
								self.lastCoinBroadcast += 1
								if self.lastCoinBroadcast < self.num_nodes:
									coin = self._broadcastCoin(self.lastCoinBroadcast)
									self.log("Broadcast my next coin flip (#{}): {}.".format(self.lastCoinBroadcast+1,coin))
									##TODO: This can never happen while the coinboard is undefined, right?
									self.ensureCoinboardPosExists(self.coinboard, self.lastCoinBroadcast, username)
									
									#while len(self.coinboard) <= self.lastCoinBroadcast:
										#self.coinboard.append({}) #extend coinboard as needed
									#self.coinboard[self.lastCoinBroadcast][username] = [coin,set()] #TODO: Should this be a sortedset()?
									self.coinboard[self.lastCoinBroadcast][username][0] = coin
									#this will overwrite any acks that were already there, but... yeah, how could acks arrive if the coin hadn't been broadcast yet?! Not a concern.		
									self.coinboard[self.lastCoinBroadcast][username][1].add(username) #acknowledge receipt of our own message.
					else:
						#if we reach the set number for someone else's flip, release reliable broadcast for the next in the series, if it exists.
						#we do this EVEN IN THE CASE OF IT BEING IN THE PAST.
						self.checkHeldCoinFlipMessages(message_i+1, message_j, searchEpoch=epoch, searchIteration=iteration)
					
				
				#a question: do we always broadcast next flip FIRST or check for while loop first?
				#probably check for while loop. broadcast next flip could also be checking held flip messages, so a lot of released messages that way. Do releases after state updates.

		
		elif mode == MessageMode.coin_list:
			if message_from_the_past:
				self.log("Throwing out old coin list message (e/i {}/{}) from {}.".format(epoch,iteration,rbid[0]))
				#old coin list messages have no use.
				return
			
			
			try:
				coin_list = data[1]
			except Exception as err:
				print err
				raise err
				#TODO: build better exception handler.
			
			if rbid[0] in self.whitelistedCoinboardList:
				self.log("Received duplicate coin list from {}: {}.".format(rbid[0],coin_list))
				return
				#duplicate coin list - we can skip this as it's already been validated.
			
			list_looks_OK, differences = self.checkListVsCoinboard(coin_list,self.coinboard,rbid[0])
			
#			 try: 
# 				for node in coin_list: #expecting list of [name,highest_i] values
# 					highest_i = node[1]
# 					if self.coinboard[highest_i][node[0]][0] is None:
# 						list_looks_OK = False #empty slot? throw out
# 					#this can also fail and fall through to the except, of course.
# 			except KeyError,ValueError,IndexError:
# 				list_looks_OK = False #the list referenced a node or whatever that our coinboard doesn't have.
# 				#this also takes care of invalid I and J errors; the coin list will just be held forever until the new iteration starts, then it get thrown out.


			
			if list_looks_OK:
				self.log("Received coin list from {}: {}.".format(rbid[0],coin_list))
				self.whitelistedCoinboardList.add(rbid[0]) #sender node name
			
				if len(self.whitelistedCoinboardList) == self.num_nodes-self.fault_bound: 
					if self.coinState == 2:
						self.log("And we are done! About to finalize coinboard.")
						#OK, it's go time! Move to stage 3.
						self.coinState = 3
						self._finalizeCoinboard()
					else: 
						self.log("Precess 2 is set; coinboard will go straight to stage 3 (done) when it hits stage 2.")
						self.precessCoinII = True
			else:
				if list_looks_OK == False:
					self.log("Holding coin list from {} for later: {}.".format(rbid[0],coin_list))
				#TODO: list_looks_OK will be None if there was an error. Handle this error.
					self.holdCoinListForLater(message, coin_list) #TODO: Will this ever trigger? Surely the checkCoinboardHolding will catch it first, right?
					return
				#hold list for later
				else: 
					self.log("Some sort of error processing coin list from {}: {}.".format(rbid[0],coin_list))
			
		else:
			self.log("Throwing out bracha or some other type of noncoin message from {} via {}.".format(rbid[0], message['sender']))
			self.log("This is NOT supposed to happen - noncoin messages aren't even supposed to hit this function. Debug time!")
			return #this can't be processed, no way no how.
	
	def logCoinFlip(self,flip_value, node, iteration):
		self.logCoinFlipSubsidiary(self.coinboardLogs,flip_value, node, iteration)
	
	
	def logPastCoinFlip(self,flip_value, node, iteration, epoch):
	#TODO: Use DeepCopy when copying.
		if epoch not in self.pastCoinboardLogs: #coinboard logs is epoch only - not iteration
			#TODO:  
			self.pastCoinboardLogs[epoch] = [{},{}] #create a storage for original and updated past coinboard. But original will always stay empty. TODO: Do proper error handling for this.
	
		thisCoinboardLogs = self.pastCoinboardLogs[epoch][1] #[0] is the original version, [1] is the updated version
		self.logCoinFlipSubsidiary(thisCoinboardLogs,flip_value, node, iteration)
	

	def logCoinFlipSubsidiary(self,thisCoinboardLogs, flip_value, node, iteration):
		if node not in thisCoinboardLogs: #set up node entry
			thisCoinboardLogs[node] = []
		if len(thisCoinboardLogs[node]) <= iteration: #set up line
			thisCoinboardLogs[node].extend([0 for _ in range(iteration - len(thisCoinboardLogs[node]) + 1)])
			#fill missing spaces with '0'
		if thisCoinboardLogs[node][iteration] is None: #set up cell
			thisCoinboardLogs[node][iteration] = 0
		thisCoinboardLogs[node][iteration] += 1 if flip_value else -1 #add
	
	def _globalCoin(self):
		global username
		self.ensureCoinboardPosExists(self.coinboard, 0, username)
		#if len(self.coinboard) < 1:
		#	self.coinboard.append({})
		#if username not in self.coinboard[0]:
		#	self.coinboard[0][username] = [None,set()] #put our first coin here
		
		coin_value = self._broadcastCoin(0)
		self.log("Broadcast my first coin flip: {}.".format(coin_value))
		
		self.coinboard[0][username][0] = coin_value #store our first coin in the coinboard
		
		if self.coinState > 0: #0 = waiting 1 = sending coins 2 = sending lists 3 = done?
			self.log("Error: Global Coin start called with Coin State >= 1.")
		else:
			if self.precessCoin: #precessCoin is basically saying that we've received info for the coinboard to go straight to state 2 already
				self.coinState = 2
				self._broadcastCoinList()
				if self.precessCoinII:
					self.coinState = 3
					self._finalizeCoinboard() 
					
			else:
				self.coinState = 1 #we're rolling!
		#we set up the coinboard here (a little)
		#we broadcast our first coin.
		#we set coinState from 0 to 1 here. Or if PrecessCoin is True, we set it to 2 here and broadcast our list!!
			
		
	
	
	def _broadcastCoin(self,message_i):
		global username, random_generator
		flip = (random_generator.random() >= .5) #True if >= .5, otherwise False. A coin toss.
		ReliableBroadcast.broadcast((MessageMode.coin_flip, message_i, username,flip),extraMeta=(self.ID,self.epoch,self.iteration))
		
		return flip #so we can use it too
		
	def _acknowledgeCoin(self,message_i,message_j):
		self.log("Acknowledged {}'s coin flip #{} ({}).".format(message_j,message_i,self.coinboard[message_i][message_j][0]))
		ReliableBroadcast.broadcast((MessageMode.coin_ack, message_i, message_j),extraMeta=(self.ID,self.epoch,self.iteration))	
		
	
	def _finalizeCoinboard(self):
		coinCount = 0	
		self.log("Finalizing coinboard.")
		#TODO: When do we generate the numpy array? Or whatever we're using.
		for node in self.coinboardLogs:
			if abs(self.coinboardLogs[node][self.iteration]) > 5 * sqrt( self.num_nodes * log(self.num_nodes) ):
				self.blacklistNode(node)
			else:
				if node in self.goodNodes: #we don't include pre-blacklisted nodes in our count.
					coinCount += self.coinboardLogs[node][self.iteration]
		
		if len(self.epochFlips) < self.iteration:
			self.epochFlips.extend([0 for _ in range(self.iteration - len(self.epochFlips))])
			
		if len(self.epochFlips) > self.iteration:
			if self.epochFlips[self.iteration] != 0:
				self.log("Uh-oh. Went to fill in the result for an interation and it was already filled in. This indicates _finalizeCoinboard was called more than once in an iteration. A bug fix will likely be necessary.")
				raise RuntimeError('called _finalizeCoinboard twice in an iteration')
				#This shouldn't happen.
			else: 
				self.epochFlips[self.iteration] = 1 if coinCount >= 0 else -1
		else:
			self.epochFlips.append(1 if coinCount >= 0 else -1)
			
		self.log("Coinboard value is {}.".format(coinCount >= 0))
		if self.useCoinValue:
			self.log("Using coinboard value.")
			self.value = (True,) if coinCount >= 0 else (False,) #the second item is the Decide flag
		else:
			self.log("Not using coinboard value (hold value).")
		#else:
			#we don't set the value here. see note early on in _brachaFinal().
			
			# find maximum number of decider messages. Is it 0 or 1 that takes the crown?
# 			num_deciding_messages = max(self.brachaMsgCtrGoodDeciding)
# 			deciding_value = self.brachaMsgCtrGoodDeciding.index(num_deciding_messages)
# 			deciding_equal = (self.brachaMsgCtrGoodDeciding[0] == self.brachaMsgCtrGoodDeciding[1])
# 			
# 			if not deciding_equal:
# 				self.value = ((True,) if deciding_value == 1 else (False,)) #if it's a tie, we stay with our previous value.
# 			else:
# 				self.value = (self.value[0],) #tie result, value carries over, decide flag doesn't
		
		#store coinboard in past coinboards here.
		self.pastCoinboards[(self.epoch,self.iteration)] = self.coinboard
		#if self.epoch not in self.pastCoinboardLogs:
		self.pastCoinboardLogs[self.epoch] = [{},{}]
		self.pastCoinboardLogs[self.epoch][0] = self.coinboardLogs
		self.pastCoinboardLogs[self.epoch][1] = deepcopy(self.coinboardLogs) #this copy will be updated if messages-from-the-past come in, and we don't want it to also update the original copy by accident.

		
		self.iteration += 1
		self._startBracha()
		#Summon next round (iteration).
		#epoch processing will be triggered in startBracha() if need be.

		
	def _broadcastCoinList(self):
		#build and send the coin list from the coinboard.
		buildingDict = {}
		#we start with a dict because we go round 1, round 2, round 3... etc
		#and so older-round items for a node in the dict will be overwritten with newer ones IF THEY EXIST.
		for index, roundI in enumerate(self.coinboard):
			for coin_j, coin_value in roundI.iteritems():
				if coin_value[0] is not None: #i.e. coin received, true or false
					buildingDict[coin_j] = index
				
		coinList = [[key,value] for key, value in buildingDict.iteritems()] #key = node name = J. value = highest round = I.
		self.log("Broadcasting my coin list: {}".format(coinList))
		#now send off the list
		ReliableBroadcast.broadcast((MessageMode.coin_list, coinList),extraMeta=(self.ID,self.epoch,self.iteration))	
		
	def blacklistNode(self,sender):
		#blacklisted nodes have their coin flips submitted to globalCoin IGNORED.
		#TODO: Are we supposed to ignore their results in bracha, too?
		#TODO: implement this.
		#if we blacklist more than t nodes, we have a serious problem. What do we do then?
		#is it possible to blacklist ourselves?
		#if we blacklist n/3 or more, or 2t or more, abort/_reset().
		pass	
		
		
	def holdForLaterEpoch(self, message, target_epoch):
		#saving a message until later. Fish saved messages out with checkHeldMessages.

		if target_epoch not in self.heldMessages['epoch']:
			self.heldMessages['epoch'][target_epoch] = blist()
		self.heldMessages['epoch'][target_epoch].append(message)
	
	def holdForLaterIteration(self,message, target_iter):
		#saving a message until later. Fish saved messages out with checkHeldMessages.

		if target_iter not in self.heldMessages['iteration']:
			self.heldMessages['iteration'][target_iter] = blist()
		self.heldMessages['iteration'][target_iter].append(message)
	
	
	def holdForLaterWaveSpecial(self, message, sender):
		#this is for holding wave 3 messages, that are not deciding messages, whose values can't be determined because their wave 2 values haven't come in yet. 
		if sender in self.heldMessages['wave3_special']:
			self.log("Problem: More than one wave 3 special hold message arrived from the same node. This shouldn't happen (messages either weren't deduplicated or the node is doing something stupid).")
		else:
			self.heldMessages['wave3_special'][sender] = []
		self.heldMessages['wave3_special'][sender].append(message)
	
	def holdForLaterWave(self, message, wave, msgValue): #number_messages_needed):
		#new ver just recalculates the number of messages needed at time and releases all.
		#saving a message until later. Fish saved messages out with checkHeldWaveMessages.
		#old ver	#self.heldMessages['wave'][wave].add( (sum(self.brachaMsgCtrTotal[wave-1])+number_messages_needed, message) )
		self.heldMessages['wave'][wave][1 if msgValue else 0].append(message)
		#the 'number_messages_needed' at the front - this number will only go DOWN as we receive more wave2/wave3 messages. (this works because held wave messages are wiped at the start of a new iteration) So the list is sorted in reverse order of the number of messages needed, and when we get a new message we just have to check the number of messages received and we're fine.
		
		#so we're putting (total messages received so far) + (num messages needed) at the front of each message. And when (total messages received) is >= that number, you pop the message.
		
	def holdCoinForLaterEpoch(self, message,target_epoch):
		#We store coin messages separately from bracha messages because they are processed differently when fishing them out.	
		
		if target_epoch not in self.heldMessages['coin_epoch']:
			self.heldMessages['coin_epoch'][target_epoch] = blist()
		self.heldMessages['coin_epoch'][target_epoch].append(message)
		
	def holdAcceptedCoinForLaterEpoch(self,message,target_epoch):
		#We store coin messages separately from bracha messages because they are processed differently when fishing them out.	
		
		if target_epoch not in self.heldMessages['coin_epoch_accepted']:
			self.heldMessages['coin_epoch_accepted'][target_epoch] = blist()
		self.heldMessages['coin_epoch_accepted'][target_epoch].append(message)
		
	def holdCoinForLaterIteration(self, message,target_iter):
		if target_iter not in self.heldMessages['coin_iteration']:
			self.heldMessages['coin_iteration'][target_iter] = blist()
		self.heldMessages['coin_iteration'][target_iter].append(message)
		
	def holdAcceptedCoinForLaterIteration(self, message,target_iter):
		if target_iter not in self.heldMessages['coin_iteration_accepted']:
			self.heldMessages['coin_iteration_accepted'][target_iter] = blist()
		self.heldMessages['coin_iteration_accepted'][target_iter].append(message)
		
	def holdCoinForSufficientAcks(self,message,message_i,message_j):
		if (self.epoch,self.iteration) not in self.heldMessages['coin_flip']:
			self.heldMessages['coin_flip'][(self.epoch,self.iteration)] = {}
			
		if (message_i,message_j) not in self.heldMessages['coin_flip'][(self.epoch,self.iteration)]:
			self.heldMessages['coin_flip'][(self.epoch,self.iteration)][(message_i,message_j)] = blist()
		#multiple messages can be stored under the same i,j - reliable broadcast creates many copies!
		self.heldMessages['coin_flip'][(self.epoch,self.iteration)][(message_i,message_j)].append(message)
		
		
	def checkListVsCoinboard(self, coinlist,coinboard,sender):
		try: 
			stuff_to_fulfill = {}
			for coin_item in coinlist: #item format: [username,highest_value] where the highest_value is the index of the last item received. So "3" means items 0-3 received, etc.
				coin_j = coin_item[0]
				coin_i = int(coin_item[1])
				if coin_j not in self.nodes:
					self.log("Error: Coin list from {} has a node {} we've never heard of that will never appear in our coinboard.".format(sender,coin_j))
					return None, None
				if type(coin_i) is not int or coin_i < 0 or coin_i >= self.num_nodes:
					self.log("Error: Coin list from {} has an invalid i ({}) on {}'s column.".format(sender,coin_i,coin_j))
					return None, None
				if coin_j in stuff_to_fulfill:
					self.log("Warning: Coin list from {} may be invalid. It has more than one entry for j {}.".format(sender,coin_j))
					if coin_i <= stuff_to_fulfill[coin_j]:
						continue #accept the higher of the two values in the duplicate
				
				if len(coinboard) < coin_i or coin_j not in self.coinboard[coin_i] or coinboard[coin_i][coin_j][0] is None: #not got to that round yet OR no entry for that node OR no value in that node's entry
					stuff_to_fulfill[coin_j] = coin_i	
				
			if len(stuff_to_fulfill) == 0:
				return True, None
				
			return False, stuff_to_fulfill
				
		except (ValueError, KeyError, IndexError):
			traceback.print_exc(None,stdout) #log it
			#self.log("Error processing coin list {}.".format(coinlist))
			#print e
			return None, None		
		
		
	def holdCoinListForLater(self, message, differences):
	
		if len(differences) == 0:
			self.log("Why are we holding the coin list from {}? It appears to be up to date.".format(message['meta']['rbid'][0]))
				
		self.heldMessages['coin_list'].append([differences,message])
		
	##This section has functions that check different held messages. Usually 'check' means 'release unconditionally', but that's not always the case.	
	
	def checkHeldEpochMessages(self,target_epoch):
		if target_epoch not in self.heldMessages['epoch']:
			return
			
		for message in self.heldMessages['epoch'][target_epoch]:
			self.validateBrachaMsg(message)
			#messages will never return here. They either go into the iteration or wave hold buckets, get processed, or get discarded.
		
		del self.heldMessages['epoch'][target_epoch]
		
	def checkHeldCoinEpochMessages(self, target_epoch):
		if target_epoch not in self.heldMessages['coin_epoch'] and target_epoch not in self.heldMessages['coin_epoch_accepted']:
			return
			
		for message in self.heldMessages['coin_epoch'][target_epoch]:
		
			#we can get the message type without trouble 'cause we already got it in a 'try' earlier.
			if message['body'][0] == MessageMode.coin_ack:
				#Throw here - ack messages aren't supposed to be held here.
				#TODO: actually throw.
				continue
			
			ReliableBroadcast.handleRBroadcast(message) #we do not set checkCoinboardMessages to 'false' here - the recheck still needs to see if the message needs acks / is a passable list / whatever.

				###Messages that are already accepted but held for epoch need to be stored SEPARATELY.

				#coin_ack messages are only held if they're early, and only on accept. 
				
			#messages will never return here, though.
		
		del self.heldMessages['coin_epoch'][target_epoch]
		
		for message in self.heldMessages['coin_epoch_accepted'][target_epoch]:
			self.validateCoinMsg(message) #messages that we've accepted just need to go back to the 'accept' thing, they don't need reliable broadcasting processing again.
		
		del self.heldMessages['coin_epoch_accepted'][target_epoch]
		
	def checkHeldIterMessages(self, target_iter):
		if target_iter not in self.heldMessages['iteration']:
			return
			
		for message in self.heldMessages['iteration'][target_iter]:
			self.validateBrachaMsg(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['iteration'][target_iter]
		
	def checkHeldCoinIterMessages(self, target_iter):
		if target_iter not in self.heldMessages['coin_iteration'] and target_iter not in self.heldMessages['coin_iteration_accepted']:
			return
			
		for message in self.heldMessages['coin_iteration'][target_iter]:
			if message['body'][0] == MessageMode.coin_ack:
				#Throw here - ack messages aren't supposed to be held here.
				raise RuntimeError('coin ack message was incorrectly held for iteration')
				
			ReliableBroadcast.handleRBroadcast(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['coin_iteration'][target_iter]
		
		for message in self.heldMessages['coin_iteration_accepted'][target_iter]:
			self.validateCoinMsg(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['coin_iteration_accepted'][target_iter]
	
	def checkHeldWaveMessagesSpecial(self, sender):
		if sender in self.heldMessages['wave3_special']:
			for message in self.heldMessages['wave3_special'][sender]:
				#messages won't be returned to the wave 3 special hold bucket if this fn is triggered.
				self.validateCoinMsg(message)
			del self.heldMessages['wave3_special'][sender]
	
	def checkHeldWaveMessages(self, wave):
		#remember, it's '[1 if msgValue else 0]
		#so [F,T] is the format of messages_found
		if wave == 2:
			messages_needed = self.initial_validation_bound
			messages_found = self.brachaMsgCtrTotal[0] 
			
		elif wave == 3:
			messages_needed = self.num_nodes // 2 + 1
			messages_found = self.brachaMsgCtrTotal[1]
		else:
			pass #TODO: throw error. Programmer screwup.
			
		for i in range(2): #0,1			
			if messages_found[i] >= messages_needed:
				for message in self.heldMessages['wave'][wave][i]:
					self.validateBrachaMsg(message)
		
				self.heldMessages['wave'][wave][i] = [] #clear messages
			
				if wave == 3:
					if debug_byz:
						lmessages = len(self.heldMessages['wave'][wave][1-i])
						if lmessages > 0:
							self.log("Throwing out {} unvalidateable wave 3 messages. This is indicative of probable adversary activity.".format(lmessages))
					self.heldMessages['wave'][wave][1-i] = [] #if we successfully processed one bucket of wave 3 messages, then the other bucket, if any, are invalid (because you can't have a majority of the other message if you had a majority of this one). So throw those out.
					break
			
			
	
		#TODO: This doesn't work. Messages can get put back in the late-wave bucket because the number of messages needed is just a minimum.
		#EDIT: This works now (probably) now that heldMessages['wave'] uses a sorted list.
# 		while len(self.heldMessages['wave'][wave]) > 0:
# 			if self.heldMessages['wave'][wave][-1][0] <= sum(self.brachaMsgCtrTotal[wave-1]):
# 				#this pulls out the message with the lowest # of messages (0) stored for the current wave held list (self.heldMessages['wave'][wave]) and checks its message counter [0] to see if we've received that many messages of the previous wave. If so, we reprocess it and repeat.
# 				message = self.heldMessages['wave'][wave].pop(0)[1]
# 				self.validateBrachaMsg(message)
# 			else:
# 				#otherwise, we end this while loop.
# 				break	
			
		
		#we can shortcut a lot of this by considering reasons messages are held:
		#future epoch
			#refresh: on new epoch (can check by number)
		#future iteration
			#refresh: on new iteration (ditto)
		#wave with not enough validated messages to pass on
			#refresh: on receiving a new message of the previous wave, or at least enough messages of the previous wave
		#This function goes through the message held list in order and feeds it to the validator one by one. We stop when we reach where the end of the message held list was when we started. Then we take only the new bit and it becomes the held messages queue.
	
	def checkHeldCoinFlipMessages(self, target_i,target_j,searchEpoch=None,searchIteration=None):
	#somewhat contrary to the name, this RELEASES held coin flip messages for the specific thing. 
	#it is only to be called if enough acknowledgements have been received for that reliable broadcast message to be participated in, as it bypasses reverification.
		if searchEpoch is None:
			searchEpoch = self.epoch
		if searchIteration is None:
			searchIteration = self.iteration
	
		if (searchEpoch,searchIteration) not in self.heldMessages['coin_flip']:
			return
		if (target_i,target_j) not in self.heldMessages['coin_flip'][(searchEpoch,searchIteration)]:
			return
			
		if len(self.heldMessages['coin_flip'][(searchEpoch,searchIteration)][(target_i,target_j)]) > 0:
			self.log("Releasing held coin flip messages for {} round {}.".format(target_j,target_i))	
			
		for message in self.heldMessages['coin_flip'][(searchEpoch,searchIteration)][(target_i,target_j)]:
			ReliableBroadcast.handleRBroadcast(message,checkCoinboardMessages=False)
		
		del self.heldMessages['coin_flip'][(searchEpoch,searchIteration)][(target_i,target_j)]
	
		
	def checkHeldCoinListMessages(self,accepted_flip_i, accepted_flip_j):
		#this releases held coin list messages given that the i and j have just been received here. 
		if len(self.heldMessages['coin_list']) > 0:
			self.log("Clearing held coin list items for this message.")
		
		messages_decremented = 0
		new_block_lengths = []
		
		for messageID in range(len(self.heldMessages['coin_list']) - 1,-1,-1): #list indices from n to 0 in reverse order
			#thisMessage = self.heldMessages['coin_list'][messageID]
			if accepted_flip_j in self.heldMessages['coin_list'][messageID][0]: #[0] is the message block's dict of stuff to do. [1] would be the actual message.
				if accepted_flip_i >= thisMessage[0][accepted_flip_j]:
					del self.heldMessages['coin_list'][messageID][0][accepted_flip_j]
					messages_decremented += 1
					new_block_lengths.append(len(self.heldMessages['coin_list'][messageID][0]))
					if len(self.heldMessages['coin_list'][messageID][0]) == 0:
						del self.heldMessages['coin_list'][messageID]
						ReliableBroadcast.handleRBroadcast(thisMessage[1], checkCoinboardMessages=False) #send the message back out and process it
						#TODO: For efficiency, this should probably be here under the check that we cleared something. But what if a {} (ready to go) list ends up here? It'll never be released. Fix this... maybe check when storing?
		
		if len(self.heldMessages['coin_list']) > 0:
			self.log("{} messages decremented. New block lengths: {}".format(messages_decremented, new_block_lengths))
		
	def clearHeldEpochMessages(self):
		#called on reset. Removes only epochs that are previous to the current epoch.
		#we're OK with wiping this on a reset, as we're completely giving up on the past epochs.
		self.heldMessages['epoch'] = { key:value for key,value in self.heldMessages['epoch'].iteritems() if key >= self.epoch}
		#bracha messages would be thrown out anyway once processed. They have no reliable broadcast holds, so deleting the old stuff is fine.
		self.heldMessages['coin_epoch'] = { key:value for key,value in self.heldMessages['coin_epoch'].iteritems() if key >= self.epoch}
		####coin messages might need to be checked. TODO. Maybe we don't call this after all?
		self.heldMessages['coin_epoch_accepted'] = { key:value for key,value in self.heldMessages['coin_epoch_accepted'].iteritems() if key >= self.epoch}
		
	def clearHeldIterMessages(self):
		#called on new epoch. 
		self.heldMessages['iteration'] = {}
		self.heldMessages['coin_iteration'] = {}
		self.heldMessages['coin_iteration_accepted'] = {}
		
	def clearHeldWaveMessages(self):
		#called on new iteration. 
		self.heldMessages['wave'] = {2:[[],[]], 3:[[],[]]}
		self.heldMessages['wave3_special'] = {}
		
	#coinboard flip messages, and by extension, coinboard epoch/iteration messages, are NEVER cleared (the latter because flip and list messages are stored together in the epoch/iter buckets and we'd want to keep the flip messages). Even if a new iteration starts, old flips will be written into the coinboard to help along anyone else who comes calling.
	
	def clearHeldCoinListMessages(self):
		#called on new iteration - if a new iteration starts, we must have r-received n - t coin lists, NOT counting whatever is in here, so every other good node will receive same. (Or we're a bad node and it doesn't matter.)
		#this works because if we've reached a new iteration, then there's enough for other nodes to do so.
		self.heldMessages['coin_list'] = []
	
	
	def _brachaWaveTwo(self):
		if self.brachaMsgCtrGood[0][0] > self.brachaMsgCtrGood[0][1]:
			self.value = (False,)
		if self.brachaMsgCtrGood[0][0] < self.brachaMsgCtrGood[0][1]:
			self.value = (True,)
			
		if self.corrupted and self.bracha_gameplan is not None and self.bracha_gameplan[1] is not None:
			self.value = (self.bracha_gameplan[1],) #pawn of the adversary says what?
				
		self.log("Moving to Bracha Wave 2: value is now {}".format(self.value[0]))	
		#if they are equal, we stay where we are.
		
		#Bracha Wave 2
		if not self.corrupted or self.bracha_gameplan is not None: #if the entire gameplan is none, don't broadcast at all.
			ReliableBroadcast.broadcast((MessageMode.bracha, 2, self.value),extraMeta=(self.ID,self.epoch,self.iteration))
		#also, count myself (free).
		self.brachabits[username][2] = self.value[0]
		
		#if self.brachabits[username][0]: #if we're a good node:
		self.brachaMsgCtrGood[1][1 if self.value[0] else 0] += 1 ### we're always a good node
		self.brachaMsgCtrTotal[1][1 if self.value[0] else 0] += 1
		
		#TODO: IMPORTANT - Broadcast SHOULD loop back, but if it does not, we need to call ValidateMessage manually. This could the last received message needed to advance to another wave...!
		
	
	def _brachaWaveThree(self):
		if self.brachaMsgCtrGood[1][0] > self.num_nodes // 2:
			self.value = (False,True) #decide
		elif self.brachaMsgCtrGood[1][1] > self.num_nodes // 2:
			self.value = (True,True) #decide
		else:
			self.value = (self.value[0],False) #no decide
			
		if self.corrupted and self.bracha_gameplan is not None and self.bracha_gameplan[2] is not None:
			if None in self.bracha_gameplan[2]: #partial overwrite
				self.protovalue = []
				for index, thisvalue in enumerate(self.bracha_gameplan[2]):
					if thisvalue is not None:
						self.protovalue.append(thisvalue)
					else:
						self.protovalue.append(self.value[index])
				self.value = tuple(self.protovalue)
			else:
				self.value = self.bracha_gameplan[2] #pawn of the adversary says what?
			#note that this one should be a two-item tuple - the adversary specifies the deciding flag, too.
			
		self.log("Moving to Bracha Wave 3: value is now {}, {}deciding".format(self.value[0],'' if self.value[1] else 'not '))
		
		#Bracha Wave 3
		if not self.corrupted or self.bracha_gameplan is not None: #if the entire gameplan is none, don't broadcast at all.
			ReliableBroadcast.broadcast((MessageMode.bracha, 3, self.value),extraMeta=(self.ID,self.epoch,self.iteration))
		#also, count myself (free).
		self.brachabits[username][3] = self.value[0]

		#if self.brachabits[username][0]: #if we're a good node:
		### we're always a good node
		self.brachaMsgCtrGood[2][1 if self.value[0] else 0] += 1
		if self.value[1]:
			self.brachaMsgCtrGoodDeciding[1 if self.value[0] else 0] += 1
		### end good block
		self.brachaMsgCtrTotal[2][1 if self.value[0] else 0] += 1
		
	
	def _brachaFinal(self):
		#brachaFinal only fires once - afterward the instance is in 'wave 4' until a new iteration starts.
		
		#find maximum number of decider messages. Is it 0 or 1 that takes the crown?
		num_deciding_messages = max(self.brachaMsgCtrGoodDeciding)
		deciding_value = self.brachaMsgCtrGoodDeciding.index(num_deciding_messages)
		if self.brachaMsgCtrGoodDeciding[1-deciding_value] > 0:
			self.log("Warning: We have {} deciding messages on the side of {} - and {} on the side of {}. This can only happen with adversarial interference.".format(num_deciding_messages,True if deciding_value == 1 else False,self.brachaMsgCtrGoodDeciding[1-deciding_value],False if deciding_value == 1 else True))
			#by default, only one of the two values can be deciding. so if we get a majority of deciding messages from one side and the other has SOME, then that indicates tampering.
		
		
		#deciding_equal = (self.brachaMsgCtrGoodDeciding[0] == self.brachaMsgCtrGoodDeciding[1])
	
		if num_deciding_messages >= self.num_nodes - self.fault_bound:
			self.log("Deciding on {}.".format(True if deciding_value == 1 else False))
			self._decide(True if deciding_value == 1 else False)
	
			return
		elif num_deciding_messages > self.fault_bound:
			#globalCoin doesn't return immediately, so we can't use its return value - nor can be start the new iteration right away. What we do instead is set up a flag so that the value is set to be captured from globalCoin... or not.
			self.useCoinValue = False
			
			self.log("Running Global-Coin, but setting value to {}.".format(True if deciding_value == 1 else False))
			#if not deciding_equal:
			self.value = ((True,) if deciding_value == 1 else (False,)) #use the value in the majority of deciding messages, NOT the value the node previously had.
			#else:
			#	self.value = (self.value[0],) #tie result, value carries over, decide flag doesn't
			
			#these cut lines of code above were cut because the correct response to deciding messages from both directions is to warn, not to handle it silently
				
			#set the new value IMMEDIATELY. Not after global-coin runs. Global-Coin takes a while, and we might get more stuff in since then, but it could screw Bracha up.
			
			self._globalCoin()
			
		else: 
			self.log("Running Global-Coin and using its value.")
			self.useCoinValue = True
			self._globalCoin()
			
			
	def _processEpoch(self):
		#the block of text at the bottom of the function is the Section 6 (polynomial) Process-Epoch algorithm. This implementation implements the Section 7 (potentially exponential) Process-Epoch algorithm.
		
		#a bit of terminology, first off:
			# M refers to a matrix of all coin flips written by all nodes in an epoch, the so-called 'god view'. This doesn't actually exist.
			# M[i,j] refers to the sum of all flips written by node j during iteration i.
			# M_p refers to a processor's own view of the same - with the blacklist taken in mind. 
			# If a node is NOT on the blacklist, M_p[i,j] is the sum of all flips from node j, received BY THE PROCESSOR P, during iteration i.
			# If a node IS on the blacklist, M_p[i,j] is forced to 0. Even if it actually isn't. 
			# TODO: Does blacklisting delete from coinboard logs?
			
			# B, or 'beta', refers to #TODO
			
			# c_1 * m refers to... well, 'm' is the number of iterations in an epoch. c1 is a constant on that - Lemma 5.5 of King-Saia suggests m as 0.001, but it also suggests using t as < n/36, so I'm not sure how accurate that is.
			# What this is supposed to be is a number used to say that, with probability near 1, there exists a set of iterations in the epoch where, if we didn't decide already, then the adversary had to VISIBLY interfere in $$$ iterations, at least.
			# We'll need to recalculate and see, depending on the number of nodes, number of iterations, and size of t, what to expect in how many iterations are guaranteed in this way.
			# Note that c_1*m may be less than the unknown number I referred to with "$$$" above, to leave room for error / ease of algorithming. But yeah, the idea is: the epoch needs to be checked over; this many iterations MUST exist where a bunch of nodes behaved adversarially and ARE CATCHABLE because of it; go catch them.
			
		#the steps of this algorithm are as follows:
		
		#1. If a processor p (self) finds a set of processors S (#TODO), of size t (self.fault_bound) or less, and a set of iterations I (#TODO) of size c_1*m (#TODO) or less, such that for EACH iteration in the set, [ the absolute value of the sum of flips from all processors in S >= Beta/2 ]:
		
			#(This is actually the hardest part of the algorithm. The paper doesn't say HOW to do it. It just says 'Here we assume that a set will be found if it exists, and it may take exponential time.' Like, OK.)
			
			#More thoughts on this: "In each iteration, there is a "correct direction" that is unknown to the algorithm. If the global coin is in the correct direction for enough good processors, then Algorithm 1 will succeed in the next iteration." - section 3.1 of King-Saia 
			#We can't be sure of the true correct direction- there's ways for the adversary to 'split' the coin flip if it's close to neutral. But we can be sure of what we THINK the incorrect direction is, because that's the direction that we see the coin as having fell in that iteration. 
			
			#So here's a thought. For each iteration, why not try looking into:
			## Amount of times in + vs - (obvious look at if skewed)
			## Percentage of nodes favoring + vs - (favor small percentage)
		
			# We know that most iterations, adversary influence won't be detectable. So we SPECIFICALLY look for ones where it is.
			
			## ITERATION MEASURES
			
			# Likelihood: A combination of: how many nodes are on one side vs the other, and how likely is it? (balanced vs unbalanced)
			# Success: Who won the 
			
			# We can combine those to make a 'suspiciousness' index of iters.
			
			## NODE MEASURES
			
			# Blacklistability: If you sorted each processor's iteration flip history in descending order (multiplied by the sign of the iteration, ofc), would either end be blacklistable? How about a sliding window of c1*m flips? Would it be high? What would it look like?
				# I think this makes a good sorting measure. Maybe have a counter for 'blacklistable' and a second counter for 'over half'.
				
			# Balance: How often did this processor come out one side vs the other? (DON'T use as sole factor, adversary can fake it)
			# Balance II: How strong are this processor's swings in one direction vs the other? (Again, don't use as sole factor).
		
			#combine this to make a 'suspiciousness' index of nodes?
			
			## ALGORITHM (?)
			
			# Heuristic driven: Focus on 'suspicious' iters or nodes, then see if there's combs of nodes/iters (favoring suspicious) that work?
			# Backup plan: order node and iter list from most to least suspicious, then do combinations (sorted) until we find something.
		
		
		#2. Then, for each processor in the set...
		
		#3A. Take the sum of the processor's total contributions to the set. (This is multiplied by the direction of the overall push of the set: so if the set's total push is +27, and the contribution is +5, then you end up with +5. But if the set's total push is -18, and you have a contribution of -3, then the total contribution is +3, because the signs cancel. But if the set's total push is -18, and you have a contribution of 10, the total contribution is -10.)
		
		#3B. Add that sum to the processor's score.
		
		#4. If the processor's score >= 2 * ( 5*sqrt( n*ln(n) ) ) * c_1 * m, then blacklist the processor.
		
		
		########### ACTUAL FUNCTION CODE STARTS HERE, AT THIS INDENT LEVEL ############
		
		#as a first step, we need to generate two matrices from the logs, M_p and the version of M_p that has the iteration results multiplied by the sign of the iteration in question. We'll need a dict to map node names to matrix columns, because we're omitting columns that are blacklisted.
		
		goodNodeColID = 0
		nodesToCols = {}
		matrix_preassembly = []
		
		for node in self.goodNodes:
			nodesToCols[node] = goodNodeColID
			goodNodeColID += 1
			
		#there's a question	to be had about: Do we use the coinboard as it was at the time of accept, or do we get the updated version from later?
		#this is mostly relevant for iterations that weren't the last one. Additional coin flips might come in later, and so on.
		
		#Fortunately, we can toggle which one by using a single index. [0] for original, [1] for updated.
		epoch_to_process = self.pastCoinboardLogs[self.epoch][0]
		
		for node in self.goodNodes:
			if node not in epoch_to_process:
				matrix_preassembly.append([0 for _ in range(self.maxIterations)])
				continue
			if len(epoch_to_process[node]) < self.maxIterations:
				temp = epoch_to_process[node]
				temp.extend([0 for _ in range(self.maxIterations - len(temp))])
				matrix_preassembly.append(temp)
			else:
				matrix_preassembly.append(epoch_to_process[node])
		
		matrix_MP = np.stack(matrix_preassembly,axis=1) #the 'axis=1' means each input item in the list gets converted into a column.
		
		del matrix_preassembly #this is a BIG variable and we won't need it from hereon.
		
		#if len(self.epochFlips) < self.maxIterations:
			#self.epochFlips.extend([0 for x in range(self.maxIterations - len(self.epochFlips))])
		
		if len(self.epochFlips) < self.maxIterations or 0 in self.epochFlips:
			self.log("Error: There's iterations for which this node has NO coinboard flip result. This shouldn't be possible.")
			raise RuntimeError('Blank iterations in epoch')
			
		matrix_MP_signed = (matrix_MP.T * self.epochFlips).T #multiply each 'iteration' row by the sign of the flip result of the iteration
	
		#now we've got our two matrices, and we're ready to perform some calculations.
		
		# Also: One saving grace in all of this is quite possibly that, we don't have to find a set of EXACTLY T nodes that's got this amount in the iteration. We can find a set of LESS THAN T nodes.
		
		
		
		
		
		
		
	
	
		#TODO
		#SO here's what we're gonna do.
		#first off: we need M_p. This is the consolidated epoch coinboard. It's a dict of nodes, and each node's value is a list, where the list has a cell for each iteration. M_p[node][iteration] is the sum of all that node's coinflips DURING THAT ITERATION. Which direction they pushed and how hard.
		#A NOTE ABOUT DISTILLING THIS INTO A MATRIX: M_p[iteration][node], in that order. rows are iterations, columns are nodes. DO NOT GET THIS MIXED UP or your SVD will fall flat.
		
		#anyway, now that we have that: get the <s>determinant</s> NORM of M_p. We're gonna have to turn M_p into a matrix with a set order at some point!! (see above)
		#IF the norm >= (beta/2)*sqrt(c1*m/t) WHERE alpha = sqrt(2n(n-2t)) AND beta = alpha - 2t AND c1 = a constant (TODO) AND m >= n (m should be the number of iterations) AND t = the fault bound, but it MIGHT be < n/36 instead of n/3 here. Check with Dr King. ANYWAY IF that's true...
			#find the top right singular vector of M_p.
			#_, _, vh = numpy.linalg.svd(M_p)
			#v = get the conjugate transpose of vh
			#trsv = first column of v (MAYBE - CHECK WITH PROF!!!! <<<<< ###### ****** )
			
			#the elements of the top right singular vector are now associated with the nodes. (I'm pretty sure - TODO)
		
			#next: we need a scoreList keeping track of the score of all nodes. Now... the score STICKS BETWEEN EPOCHS. Only the total reset resets it.
			#go through the TRSV. Take the value for that node. Square it. Add it to the node's score.
			#if a node's score is >= 1, blacklist it. 
		#END IF
		#(there's) nothing to do after the if, we just return.		
		
		
	def _decide(self,value):
		#self._decide(True if deciding_value == 1 else False)
		self.decided = True
		self.decision = value #should be boolean  #True if value == 1 else False	
		MessageHandler.sendAll(self.decision,self.ID,"decide") #type override
		
		#TODO: Notify decision here.
		
	def ensureCoinboardPosExists(self, coinboard, round, source):
		while len(coinboard) <= round and len(coinboard) < self.num_nodes:
			coinboard.append({}) #add rounds as necessary
		if len(coinboard) <= round:
			return False #overlength round #
		for thru_round in range(round+1):
			if source not in coinboard[thru_round]:
				coinboard[thru_round][source] = [None,set()]
		return True
		
		
	def checkCoinboardMessageHolding(self,message):
		#this only checks and holds messages for coinboard reasons (i.e. not for epoch/iteration reasons. Mind you, any message held for epoch/iteration reasons could probably ALSO be held for coinboard reasons, so...)
		
		#it's worth noting that coinboard holding procs in the reliable broadcast itself.
		#this means it takes place BEFORE epoch/iteration holding. 
		
		#reminder: rbid = sender, counter, extraMeta. 
		#extraMeta = byzID, epoch, iteration.
		#if self.decided: 
		#	return False #I've decided, I'm not accepting any more coinboard messages
		#TODO: Can I really include the above? I'm relying on Bracha's lemma which states that all good nodes agree this turn OR next turn OR all good nodes run global-coin - in which case if this decides, we don't 
				
			
		#since a coinboard instance is associated with a byzantine instance AND an epoch AND a specific iteration, we need epoch and iteration holds as well as the rbid interrupts.
		try:
			messageOrigSender = message['meta']['rbid'][0]
		except (TypeError, IndexError):
			self.log("Couldn't read reliable message with bad RBID.")
			return False

		try:
			messageExtraMeta = message['meta']['rbid'][2]
			messageEpoch = messageExtraMeta[1]
			messageIteration = messageExtraMeta[2]
			messageCoinMode = message['body'][0]
			#messageOrigSender = message['meta']['rbid'][0]
			if messageCoinMode == MessageMode.coin_flip:
				message_i = message['body'][1]
				message_j = message['body'][2]
			if messageCoinMode == MessageMode.coin_list:
				message_list = message['body'][1]
		except (TypeError, ValueError, IndexError):
			self.log("Value error. Reliable? message from {} via {} had to be discarded.".format(messageOrigSender, message['sender']))
			return False #TODO: Is 'discard' the best thing here?
		
		search_past = False
		
		
		if messageCoinMode == MessageMode.coin_flip:
			search_past = False
			if message_i == 0: #i.e. round #1
				#TODO: Message I's start at 0. Does everyone know this?
				return True #we always accept i' == 1 messages
			else: 
				if self.epoch > messageEpoch:
					search_past = True
					#early message - look up past 
				elif self.epoch < messageEpoch: 
					self.holdCoinForLaterEpoch(message,messageEpoch) #TODO: release at START of target epoch - coinboard might be set up early for this sort of thing.
					return False #we're done here
				else: #epochs match
					if self.iteration > messageIteration:
						search_past = True
					elif self.iteration < messageIteration:
						self.holdCoinForLaterIteration(message,messageEpoch) #TODO: again, release at START of target iteration.
						return False 
				try:
					#get how many acks there are for the PREVIOUS message.
					if search_past:
						if self.ensureCoinboardPosExists(self.pastCoinboards[(messageEpoch,messageIteration)], message_i-1, messageOrigSender):
							acks_count = len(self.pastCoinboards[(messageEpoch,messageIteration)][message_i-1][messageOrigSender][1])
						else:
							self.log("Couldn't accept {}'s coin flip message - impossible round (i) number for previous round: {}.".format(messageOrigSender,message_i))
							return False
					else:
						if self.ensureCoinboardPosExists(self.coinboard, message_i-1, messageOrigSender):
							acks_count = len(self.coinboard[message_i-1][messageOrigSender][1])
						else:
							self.log("Couldn't accept {}'s coin flip message - impossible round (i) number for previous round: {}.".format(messageOrigSender,message_i))
							return False
				except Exception as err:
					print err 
					raise err
					#TODO: What kind of exceptions do we run into here?
					
				if acks_count >= self.num_nodes - self.fault_bound:
					#let it go through
					return True
				else: 
					self.log("Holding {}'s coin flip message #{} - waiting for acknowledgements for previous message.".format(messageOrigSender, message_i))
					self.holdCoinForSufficientAcks(message,message_i,message_j)
					return False
		elif messageCoinMode == MessageMode.coin_list:	
			search_past = False
			if self.epoch > messageEpoch:
				search_past = True
			elif self.epoch < messageEpoch:
				self.holdCoinForLaterEpoch(message,messageEpoch) #when messages are released they'll be run back through this so we can use the same hold for both.
				return False
			else: 
				if self.iteration > messageIteration:
					search_past = True
				elif self.iteration < messageIteration:
					self.holdCoinForLaterIteration(message,messageIteration) #TODO: again, release at START of target iteration.
					return False
			try: 
				if search_past:
					result, differences = self.checkListVsCoinboard(message_list, self.pastCoinboards[(messageEpoch, messageIteration)], messageOrigSender)
				else:
					result, differences = self.checkListVsCoinboard(message_list, self.coinboard, messageOrigSender) 
					
				if result is None:
					self.log("Error processing coin list from {}.".format(messageOrigSender))
					return False
				if not result:
					self.log("Holding coin list from {} for later - differences are {}.".format(messageOrigSender,differences))
					self.holdCoinListForLater(message,differences)
				return result #passed? T/F
			except Exception as err:
				print err
				raise err
				#TODO: What kind of exceptions do we run into here?
				
	
		
		
def getAllNodes():
	#and here we end up with another pickle: for byzantine agreement to WORK, every node needs to know how many other nodes there are and what they are called.
	#the instance also needs its node list to stay stable for the term of agreement. Nodes can't join in the middle of an agreement instance!
	#this is the answer. When called, it gives the node list AT THE TIME OF THE CALL. Then that sticks to the instance object thereafter.
	
	#MODULAR - this function is modular and is expected to be swapped out given whatever's your requirements.
	return all_nodes


def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	#TODO: This code is really, really, REALLY stale by now.
	print "Starting up..."
	global username, num_nodes, fault_bound, all_nodes
		
	
	username = args[0]
	with open(args[1]) as node_list:
		all_nodes = [line.rstrip() for line in node_list]
	
	MessageHandler.init(username,"node")
	
	num_nodes = len(all_nodes)
	fault_bound = (num_nodes - 1) // 3  #t < n/3. Not <=.
	print "Maximum adversarial nodes: {}/{}.".format(fault_bound, num_nodes)
	ReliableBroadcast.initial_setup(num_nodes)
	
	weSaidNoMessages = False 
	while True:
		#print "Checking for messages."
		while True: 
			adv_message = MessageHandler.receive_backchannel()
			if adv_message is None:
				break
			#messages from the adversarial filtering backchannel are treated as accepted immediately.

			if debug_rb_accept:
				print "Accepted filtered message: "+repr(adv_message)
				stdout.flush() #force write
			msgModeTemp = adv_message['body'][0]

			thisInstance = ByzantineAgreement.getInstance(adv_message['meta']['rbid'][2][0]) #= byzID
							
			if thisInstance is None: #instance not gotten
				continue #get outta here			

			if msgModeTemp == MessageMode.bracha:
				thisInstance.validateBrachaMsg(adv_message)
				#TODO call bracha message verify function
			elif msgModeTemp == MessageMode.coin_flip or msgModeTemp == MessageMode.coin_list or msgModeTemp == MessageMode.coin_ack:
				thisInstance.validateCoinMsg(adv_message)
		
		#now check for regular messages
		message = MessageHandler.receive_next()
		if message is None:
			if not weSaidNoMessages: #only say 'nobody home' once until we receive messages again.
				print "No messages."
				weSaidNoMessages = True
			sleep(1) #wait a second before we check again.
		else:
			weSaidNoMessages = False
			#print message.headers
			#print message.body

			# message format: {'body': message.decode(), 'type': message.headers.type, 'sender': message.headers.sender, 'meta': message.headers.meta}

			
			if message['type'] == "client":
				#TODO - client messages.
				code = message['meta']['code']
				if code == "broadcast":
					print "Client message received: broadcast {}.".format(repr(message['body']))
					ReliableBroadcast.broadcast(message['body'])
				elif code == "byzantine":
					#a conundrum. How do nodes AGREE to start a byzantine agreement instance?
					#for the time being, the client notifies every node and gives them an initial value - ideal for testing.
					#in a real world distributed system, this would be through some other kind of context.
					byzID = message['meta']['byzID'] #byzantine instance ID
					byzValue = message['body'] #starting value
					
					#TODO: May have fluffed class instantiation.
					print "Byzantine message received: ID {}, value {}.".format(byzID, byzValue)
					ByzantineAgreement(byzID, byzValue)
				elif code == "message":
					#just a message to say.
					print "Client message: {}".format(message['body'])
					stdout.fflush()
				else:
					print "Unknown client message received - code: {}.".format(message['meta']['code'])
					print repr(message) #no other types of client messages implemented yet.
			
			elif message['type'] == "node":
				#reliable broadcast message format: 
				#metadata has type.
				
				#msgType = message['body'][0]
				#if msgType == "rBroadcast":
				if 'phase' in message['meta'] and 'rbid' in message['meta']: #indicating a reliable broadcast message
					result = ReliableBroadcast.handleRBroadcast(message)
					if result is not None:
						#result from Accept. Do stuff.
						is_byzantine_related = False
						if isinstance(result['body'][0],collections.Sequence) and len(result['body']) > 0 and (result['body'][0] == MessageMode.coin_flip or result['body'][0] == MessageMode.coin_list or result['body'][0] == MessageMode.coin_ack or result['body'][0] == MessageMode.bracha):
							is_byzantine_related = True
						
						if is_byzantine_related: #type(result['body'][0]) is MessageMode:
							if debug_rb_accept:
								print "About to filter accepted message: "+repr(result)
								stdout.flush() #force write
							
							#what we need to do here IS: 
							#strip out everything but the actual message and relevant headers (maybe already done?) - yeah, already done
							#figure out WHICH BYZANTINE INSTANCE the message belongs to
							thisInstance = ByzantineAgreement.getInstance(result['meta']['rbid'][2][0]) #= byzID
							
							if thisInstance is None: #instance not gotten
								continue #get outta here
							
							#now the message goes to the adversary for filtering.
							MessageHandler.sendToAdversary(result['body'],result['meta'],type_override='timing')
							
					
						else:
							#If it's a message without a MessageMode, we just print it.
							print "Accepted reliable broadcast from {}: {}".format(message['meta']['rbid'][0],message['body'])
							
				else:
					print "Unknown node message received."
					print repr(message) #TODO: throw error on junk message. Or just drop it.
			elif message['type'] == "adversary_command":
				#adversarial override - TO DO
				if message['body'][0] == "gameplan":
					thisInstance = ByzantineAgreement.getInstance(message['body'][1])
					print "I'm corrupted for iteration {} now. Gameplan: {}.".format(message['body'][1], message['body'][2])
					thisInstance.corrupted = True #Having a gameplan also bypasses certain message validation sequences. This is determined by this flag.
					thisInstance.bracha_gameplan = message['body'][2]
					#thisInstance.coin_gameplan = message['body'][3] #TODOOOOOOOOO
					thisInstance._startBracha() #start over with wave 1 message; adversary will toss not-yet-corrupted messages
					#gameplan format for corrupted nodes:
					#[0]: "gameplan"
					#[1]: Byzantine ID the node is corrupted for.
					#[2]: Bracha values. List of three values, the last including the deciding flag. Ex. [True, False, (False,True)]. If any value in the list is None, the node just acts natural. If the entire list is None, the node refuses to participate in bracha.
					#[3]: Coin values. Ignored for now.
					
					
				pass
			elif message['type'] == "decide":
				#someone's deciding - IGNORE
				pass
			elif message['type'] == "announce":
				#announce to client - IGNORE
				pass
			elif message['type'] == "halt":
				#this is for local-machine testing purposes only - it makes every node exit. Assume the adversary can't do this.
				MessageHandler.shutdown()
				exit(0)
			else: 
				print "Unknown message received."
				print repr(message)
				print type #malformed headers! Throw an error? Drop? Request resend?
				
			
				

# 		message = raw_input("Enter a destination and message. > ")
# 		if message != "":
# 			try:
# 				dest, message2 = split(message,None,1)
# 				dest = int(dest)
# 				MessageHandler.send(message2,dest)
# 				print "Message sent to "+str(dest)+"."
# 			except ValueError:
# 				MessageHandler.sendAll(message)
# 				print "Message sent to all nodes."
		
if __name__ == "__main__":
	main(argv[1:])	
else:
	print "Node script loaded."
	#print "Running as {}, dunno what to do.".format(__name__)
	#exit()