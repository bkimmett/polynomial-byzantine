#!/usr/bin/env python

from __future__ import division
from sys import argv
from time import sleep
from math import floor
import multibyz_kingsaia_network as MessageHandler
#getting an error with the above line? 'pip install kombu'
from enum import Enum
#getting an error with the above line? 'pip install enum34'
from blist import blist, btuple, sortedlist
#getting an error with the above line? 'pip install blist'

#debug logging

debug_rb = True
debug_byz = True


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
fault_bound = 0
message_counter = 0



	
		
class ReliableBroadcast:
	
	broadcasting_echoes = {}
	
	RBPhase = Enum('RBPhase',['initial','echo','ready','done'])
	#a note on these phases: the first three are used to tag individual reliable broadcast messages, BUT ALSO all four are used to indicate what state a node is in for this reliable broadcast instance: "I just sent THIS type of message" (or 'I received this one' in the case of Initial) or "I'm done!"
	
	#timeout protocol: set most recent update time and if that times out without broadcast completing, we junk it.
	
	
	#TODO: if receiving receives a message from a node not currently in the network, it should store that in case of that node joining later (and the join being late).
	#rev: FLEXNODE
	
	@classmethod
	def setupRbroadcastEcho(thisClass,uid):
		
		thisClass.broadcasting_echoes[uid] = [False, set(), set(), 1] #no initial received, no echoes received, no readies received, Phase no. 1
		print "Setting up broadcast tracking entry for key < {} >.".format(repr(uid))
	
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
		
		MessageHandler.sendAll(message,{'phase':RBPhase.initial,'rbid':(username,message_counter,extraMeta)})
		#MessageHandler.sendAll(("rBroadcast","initial",(username, message_counter, message),None),("rBroadcast","initial",username, message_counter,)) 
		print "SENDING INITIAL reliable broadcast message for key < {} > to all.".format(repr(message))
		message_counter += 1
		#We don't need to call setupRbroadcastEcho yet. The first person to receive the 'initial' message will be-- us! And it'll happen then.
	
	
	@classmethod
	def handleRBroadcast(thisClass,message):
		
		#new message format = 
		
		#{'body': message.decode(), 'type': message.headers.type, 'sender': message.headers.sender, 'meta': message.headers.meta}
		
		#meta format: {'phase':RBPhase.initial,'rbid':(username,message_counter,extraMeta)}
					
		
		sender = message['sender'] #error?: malformed data
		data, debuginfo = message['body'] #first var is used for type, skip that
		phase = message['meta']['phase']
		rbid = message['meta']['rbid'] #RBID doesn't change after it's set by the initial sender.
		
		data = tuple(data) #bug fix: for some reason tuples are decoded into lists upon receipt. No idea why.
		
		
		if phase == RBPhase.initial and sender != rbid[0]:
			#We have a forged initial message. Throw.
			print "Received forged initial reliable broadcast message from node {} ().".format(sender)
			#TODO: actually throw.
			return
			
		#TODO: Security measure. If an Initial message says (in the UID) it is from sender A, and the sender data says it is from sender B, throw an exception based on security grounds. Maybe dump that message. Effectively, that node is acting maliciously.
		#rev: PASSWALL
		#This is only applicable once we move away from prototype code.
		
		uid = tuple(rbid,data) #for storage in the log
		
	
		
		if uid not in thisClass.broadcasting_echoes:
			thisClass.setupRbroadcastEcho(uid) #TODO: A concern is that a spurious entry could be created after [A] a finished entry is removed and a message arrives late, [B] a malformed entry arrives [C] a malicious entry arrives. In the real world, is there a timeout for rbroadcast pruning? (something on the line of a day to a week, something REALLY BIG) How much storage space for rbroadcast info do we HAVE, anyway?
			
			#there's also the concern that if a node shuts down (unexpectedly?) it loses all broadcast info. Could be resolved by just counting that node towards the fault bound OR semipersistently storing broadcast info.
		
		
		
		#by using sets of sender ids, receiving ignores COPIES of messages to avoid adversaries trying to pull a replay attack.
		
		if phase == RBPhase.initial:
			thisClass.broadcasting_echoes[uid][0] = True #initial received!!
			print "Received INITIAL reliable broadcast message for key < {} > from node {}.".format(repr(uid),sender)
		elif phase == RBPhase.echo:
			thisClass.broadcasting_echoes[uid][1].add(sender)
			print "Received ECHO reliable broadcast message for key < {} > from node {}.".format(repr(data),sender)
			if thisClass.broadcasting_echoes[uid][3] == 1 or thisClass.broadcasting_echoes[uid][3] == 2:
				print "{}/{} of {} echo messages so far.".format(len(thisClass.broadcasting_echoes[uid][1]), (num_nodes + fault_bound) / 2, num_nodes) #print how many echoes we need to advance
			else:
				print "{} of {} echo messages.".format(len(thisClass.broadcasting_echoes[uid][1]), num_nodes) #just print how many echoes
		elif phase == RBPhase.ready:
			thisClass.broadcasting_echoes[uid][2].add(sender)
			
			if debug_rb:
				print "Received READY reliable broadcast message for key < {} > from node {}.".format(repr(data),sender)
				if thisClass.broadcasting_echoes[uid][3] == 1 or thisClass.broadcasting_echoes[uid][3] == 2:
					print "{}/{} of {} ready messages so far.".format(len(thisClass.broadcasting_echoes[uid][2]), fault_bound + 1, num_nodes) #print how many readies we need to advance
				elif thisClass.broadcasting_echoes[uid][3] == 3:
					print "{}/{} of {} ready messages so far.".format(len(thisClass.broadcasting_echoes[uid][2]), fault_bound*2 + 1, num_nodes) #print how many readies we need to accept
				else: 
					print "{} of {} ready messages.".format(len(thisClass.broadcasting_echoes[uid][2]), num_nodes) #print how many readies we got
		else:
			if debug_rb:
				print "Received invalid reliable broadcast message from node {} ().".format(sender,phase)
			pass #error!: throw exception for malformed data
			
		return thisClass.checkRbroadcastEcho(data,rbid,uid) #runs 'check message' until it decides we're done handling any sort of necessary sending
	
	@classmethod
	def checkRbroadcastEcho(thisClass,data,rbid,uid):
		
		#TODO: A concern - (num_nodes + fault_bound) / 2 on a noninteger fault_bound?
		
		#BROADCAST FORMAT:
		#MessageHandler.sendAll(message,{'phase':RBPhase.initial,'rbid':(username,message_counter,extraMeta)})
					
		if thisClass.broadcasting_echoes[uid][3] == RBPhase.initial:
			#waiting to send echo
			if thisClass.broadcasting_echoes[uid][0] or len(thisClass.broadcasting_echoes[uid][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[uid][2]) >= fault_bound + 1: #one initial OR (n+t)/2 echoes OR t+1 readies
				#ECHO!
				if debug_rb:
					print "SENDING ECHO reliable broadcast message for key < {} > to all.".format(repr(data))
				MessageHandler.sendAll(data,{'phase':RBPhase.echo,'rbid':rbid})
				#MessageHandler.sendAll(("rBroadcast","echo",data,None)) 
				#4th item in message is debug info
				thisClass.broadcasting_echoes[uid][3] = RBPhase.echo #update node phase
			else:
				return #have to wait for more messages
				
		if thisClass.broadcasting_echoes[uid][3] == RBPhase.echo:
			#waiting to send ready
			if len(thisClass.broadcasting_echoes[uid][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[uid][2]) >= fault_bound + 1: #(n+t)/2 echoes OR t+1 readies
				#READY!
				if debug_rb:
					print "SENDING READY reliable broadcast message for key < {} > to all.".format(repr(data))
				MessageHandler.sendAll(data,{'phase':RBPhase.ready,'rbid':rbid})
				#MessageHandler.sendAll(("rBroadcast","ready",data,None)) #message format: type, [phase, data, debuginfo]
				thisClass.broadcasting_echoes[uid][3] = RBPhase.ready #update node phase
			else:
				return #have to wait for more messages
				
		if thisClass.broadcasting_echoes[uid][3] == RBPhase.ready:
			#waiting to accept
			if len(thisClass.broadcasting_echoes[uid][2]) >= fault_bound*2 + 1: #2t+1 readies only
				#ACCEPT!
				thisClass.broadcasting_echoes[uid][3] = RBPhase.done
				return thisClass.acceptRbroadcast(data,rbid)
			else:
				return #wait for more messages!
		
		if thisClass.broadcasting_echoes[uid][3] == RBPhase.done:
			return #we've already accepted this. no further processing.
		else:
			pass #error! throw exception for malformed data in here. How'd THIS happen?			

	
	@classmethod
	def acceptRbroadcast(thisClass,data,rbid):	
		return data,rbid
		pass
		#what does accepting a r-broadcasted message LOOK like? Well, the message is confirmed to be broadcast, and is passed on to the other parts of the program.
		
		#what in Byzantine uses RB:
		
		#what in Byzantine doesn't:
		

class ByzantineAgreement:

	MessageMode = Enum('MessageMode',['bracha','coin_flip','coin_ack','coin_list'])
	
	byzantine_list = {}
	
	@classmethod
	def getInstance(thisClass,byzID):
		return thisClass.byzantine_list[tuple(byzID)]
		
	@classmethod
	def setInstance(thisClass,byzID,object):
		thisClass.byzantine_list[tuple(byzID)] = object
		
	#TODO: Add a method for list removal later.

	def __init__(self,byzID,byzValue,epochConst=1,iterConst=2):
		self.ID = byzID
		#TODO: Split what happens next by if the Value is True/False (a single-valued byzantine) or something else (a multi-valued byzantine).
		self.value = (byzValue,) #a tuple!
		self.origValue = (byzValue,)
		#ASSUMPTION: For now, value should be True or False: a single-valued byzantine thing.
		
		self.epoch = 1 #epoch = 1 to maxEpochs. If a reset occurs, we start at maxEpochs+1, +2, +3, etc.
		self.heldMessages = {'epoch':{}, 'iteration':{}, 'wave':{2:sortedlist(key=lambda x: x[0]), 3:sortedlist(key=lambda x: x[0])}}
		
		self.decided = False
		self.decision = None
		
		
		self.nodes = blist(getAllNodes()) #expecting a tuple of node IDs to be returned. This is never edited after.
		
		self.num_nodes = len(self.nodes)
		self.fault_bound = floor((self.num_nodes-1)/3) #n >= 3t+1  - this variable is 't'
		self.initial_validation_bound = (self.num_nodes - self.fault_bound) // 2 + 1 # (n - t) / 2 + 1. Used to validate wave 2 bracha messages. Never changes even as nodes are blacklisted from our end, because we can't assume the size of other nodes' blacklists because: 
		#the condition for validating a wave 2 message is that the node that sent the message had to have received some combination of wave 1 messages that could have made it send a wave 2 message.
		#which in this case is they received n - t messages, and over half that many (a majority) were for the set value. So we just need (n - t) // 2 + 1 messages to be in the chosen value.
		#this happens to be about equal to t+1 messages, with t at worst case.
		
		self.maxIterations = len(self.nodes)
		self.maxEpochs = epochConst * len(self.nodes) 
		
		self._reset() #sets up rewindable parts of agreement attempt.
		
		setInstance(self) #TODO: Yeah, is this gonna work?
		
		self._startEpoch()
		
	
	def _reset(self):
		if self.decided: #inactive after decision
			return 
		self.value = copy.deepcopy(self.origValue) #reset value to start.
		#TODO: Does reset() need to reset the node's initial value? This code assumes 'yes'. Otherwise, delete the above line.
		self.goodNodes = blist(self.nodes) #reset whitelist
		self.badNodes = [] #we need this to validate messages from other nodes 
		self.scores = [0 for node in self.nodes] #reset list of scores
		
		self.coinboard = [] #erase coin records
		
		#a few notes on how the byzantine algorithm works and using fake multithreading
		#(aka 'event-driven programming')...
		#Start Epoch starts Bracha.
		#Bracha broadcasts the first wave and RETURNS until enough Wave 1 messages are validated.
		#then we set the byzValue and broadcast the second wave... yeah.
		#receiving bracha broadcast messages acts as a handler. 
		#this handler will trigger bracha next wave if necessary.
	
	def _startEpoch():
		if self.decided: #inactive after decision
			return 
		if self.epoch > self.maxEpochs:
			#wut-oh. Reset!	
			#TODO
			return
			
		##### VERY IMPORTANT: We are assuming that there are exactly n iterations in an epoch. The original paper has m = Big-Theta(n) as the limit instead, and later on suggests m >= n for statistical analysis to work. What's the REAL max value of M?
		self.iteration = 1
		self.clearHeldIterMessages()
		
		_startBracha()
		
	def _startBracha():
		if self.decided: #inactive after decision
			return 
		if self.iteration > self.maxIterations: #nvm, start a new EPOCH instead
			#TODO: call process epoch
			self._processEpoch()
			self.epoch += 1
			self._startEpoch()
			return	
		#starts an iteration.
		self.brachabits = {node: (True, None, None, None) for node in self.goodNodes}
		self.brachabits.update({node: (False, None, None, None) for node in self.badNodes})
		#above is message storage for validation purposes
		#add a slot for each good node (first dict) and append slots for bad nodes to it (the .update part).
		#potential perils: if somehow a bad node and a good node have the same identifier (which SHOULD be addressed and filtered for elsewhere), the entry for the bad node will overwrite that of the good one.
		#but that proposes a breakdown of some sort earlier, as node names REALLY SHOULD be unique.
		self.brachaMsgCtrGood = [[0,0],[0,0],[0,0]]
		self.brachaMsgCtrTotal = [[0,0],[0,0],[0,0]]
		self.brachaMsgCtrGoodDeciding = [0,0]
		#these are counters. They count the total number of verified messages with their value of False [0] and True [0], for each of waves 1, 2, 3.
		#the third counter counts only the verified messages from good nodes that have indicated they are ready to decide.
		
		#aka Bracha Wave 1
		ReliableBroadcast.broadcast((MessageMode.bracha, 1, self.value),extraMeta=(self.ID,self.epoch,self.iteration)):
		#also, count myself (free).
		self.brachabits['username'][1] = self.value
		if self.brachabits['username'][0]: #if we're a good node:
			self.brachaMsgCtrGood[0][1 if self.value else 0] += 1
		self.brachaMsgCtrTotal[0][1 if self.value else 0] += 1
		
		#after we send our own message, we might as well check to see if there's any messages waiting.
		if self.iteration == 1:
			self.checkHeldEpochMessages(self.epoch)
		else:
			self.checkHeldIterMessages(self.iteration)
		self.wave = 1
		self.clearHeldWaveMessages()
		
		
	def validateBrachaMsg(message):	
		if self.decided: #inactive after decision
			return 
		#TODO: Better validation of bracha-style messages.
		try:
			extraMeta = message['meta']['rbid'][2]
			remoteByzID = extraMeta[0]
			if self.ID != remoteByzID:
				if debug_byz:
					print "Throwing out bracha message from {} with wrong Byzantine ID {} vs {}.".format(message['sender'],remoteByzID,self.ID)
					print "You should probably check your message routing. This isn't supposed to happen."
				return #throw out message. Somehow it was sent to the wrong iteration of byzantine agreement. How did this even happen?
			
			##Check Epoch
			epoch = int(extraMeta[1])
			if epoch < self.epoch:
				if debug_byz:
					print "Throwing out old bracha message from {}, epoch {} vs {}.".format(message['sender'],epoch,self.epoch)
				return #throw out message - it's old and can't be used
			if epoch > self.epoch:
				if debug_byz:
					print "Holding too-new bracha message from {}, epoch {} vs {}.".format(message['sender'],epoch,self.epoch)
				self.holdForLaterEpoch(message)
				return #this message can't be processed yet, it's from a different epoch entirely
			
			##Check Iteration
			iteration = int(extraMeta[2])
			if iteration > self.maxIterations:
				#a note about this part: one of the flaws in byzantine agreement is it assumes EVERY NODE KNOWS HOW MANY NODES THERE ARE AND WHO THEY ARE. If you're gonna add nodes to the network in real time you're probably going to have to do it BY byzantine agreement or a trusted third party, and then it'll take some nontrivial management to make sure enough nodes' node lists stay synchronized.
				#one thing this code DOES NOT ACCOUNT FOR is how to handle the effects of nodes joining and leaving in a resilient manner. As the classic textbook line goes, this is "left to the reader as an exercise". Sorry!
				#the reason I'm mentioning this here is that one of the reasons the below scenario can take place is that some nodes got the memo about a new node joining when this agreement instance started - and some (this one!) didn't.
				if debug_byz:
					print "Throwing out impossible bracha message from {}, iteration {} (max {}).".format(message['sender'],iteration,self.maxIterations)
					print "This can indicate a fault or nodes that are not uniformly configured with a maximum iteration limit (or nodes that have a different node list than this node at the start of the byzantine bit)."
				return #this can't be processed, it's from an iteration that's not supposed to happen.
			if iteration > self.iteration:
				if debug_byz:
					print "Holding too-new bracha message from {}, iteration {} vs {}.".format(message['sender'],iteration,self.iteration)
				self.holdForLaterIteration(message)
				return #this message can't be processed yet, maybe next (or some later) iteration
			if iteration < self.iteration:
				if debug_byz:
					print "Throwing out old bracha message from {}, iteration {} vs {}.".format(message['sender'],iteration,self.iteration)
				return #this message is from a past iteration that already concluded and is thus stale.
			
			##Check Wave
			wave = int(message['body'][1])
			if wave != 1 and wave != 2 and wave != 3:
				if debug_byz:
					print "Throwing out impossible bracha message from {}, invalid wave {}.".format(message['sender'],wave)
				return #wave can only be one, two, or three. period.
			
			msgValue = message['body'][2]
			if not isinstance(msgValue, tuple) or (length(msgValue) not in [1,2]) or not all(type(item) is bool for item in items):
				#must be a tuple of 1 or 2 items. First item is value. Second item is wave 3 'decide' flag. Decide flag is ignored if it's a wave1/wave2 message.
				if debug_byz:
					print "Throwing out impossible bracha message from {}, invalid message type {}.".format(message['sender'],type(msgValue))
				return
			
		except TypeError, ValueError, IndexError:
			if debug_byz:
				print "Value error. Message from {} had to be discarded.".format(message['sender'])
			return 
			
		#unpack msgValue	
		if wave == 3:
			msgDecide = msgValue[1]
		msgValue = msgValue[0]
		
		
		#validating time! 
		
		if wave == 1:
			#wave 1 messages are always valid.
			pass
		elif wave == 2:
			if self.brachaMsgCtrTotal[0][1 if msgValue else 0] < self.initial_validation_bound:
				#message isn't valid - we haven't received enough appropriate wave 1 messages.
				#we hold the message if there is the *potential* for there to be enough wave 1 messages. Otherwise we throw it out.
				if self.num_nodes - sum(self.brachaMsgCtrTotal[0]) + self.brachaMsgCtrTotal[0][1 if msgValue else 0] >= self.initial_validation_bound:
					#...but we COULD hit it later.
					if debug_byz:
						print "Holding uncertain wave 2 bracha message from {}, might not have enough wave 1 messages to validate {}.".format(message['sender'],msgValue)
					self.holdForLaterWave(message, 2, self.initial_validation_bound - self.brachaMsgCtrTotal[0][1 if msgValue else 0])
				else:
					#...and we're not going to be able to hit it in this go-round.
					if debug_byz:
						print "Discarding unvalidateable wave 2 bracha message from {}, not enough wave 1 messages to validate {}.".format(message['sender'],msgValue)
					return
				
				
			#wave 2 messages are valid IF we received at least n - t wave 1 messages (from any nodes) AND a majority of those n - t is for the value listed in the wave 2 message.
			#this is complicated somewhat by the fact that n - t >= 2t + 1. So the number of values we need for a 'majority' is actually (n - t) // 2 + 1. Or, about t+1. So it's possible for enough wave 1 messages to come in that wave 2 messages taking either position are viable.
		elif wave == 3:
			#wave 3 messages are more straightforward to validate - more than half of the nodes have to have settled to a pattern. This is quite unequivocal. 
			if not msgDecide:
				if msgValue != self.brachabits[message['sender']][2] or self.brachaMsgCtrTotal[1][1 if msgValue else 0] >= self.num_nodes // 2 + self.fault_bound + 1:
					#basically, if 'decide' is false, two things must be true:
					#1. The node must have the same value as its Wave 2 message.
					#2A. There must not be more than n//2 + t nodes that have a specific value in their wave 2 message, as if there were, such a hypermajority would force the node to set 'decide' to true and their value to that value.
					#2B. This second condition is hard to hit as it requires this node receive more than n - t messages, but I'm including it just in case as it is a condition to check for.
					if debug_byz:
						print "Discarding unvalidateable wave 3 bracha message from {}, sender is not deciding and {} {}.".format(message['sender'], "changed value to" if msgValue != self.brachabits[message['sender']][2] else "would be forced to decide", msgValue)
					#TODO: Maybe blacklist here?
					return
			
			if msgDecide and self.brachaMsgCtrTotal[1][1 if msgValue else 0] <= self.num_nodes // 2:
				#message isn't valid - we haven't received enough appropriate wave 2 messages.
				#we hold the message if there is the *potential* for there to be enough wave 1 messages. Otherwise we throw it out.
				if self.num_nodes - sum(self.brachaMsgCtrTotal[1]) + self.brachaMsgCtrTotal[1][1 if msgValue else 0] > self.num_nodes // 2:
					#...but we COULD hit it later.
					if debug_byz:
						print "Holding uncertain wave 3 bracha message from {}, might not have enough wave 2 messages to validate {}.".format(message['sender'],msgValue)
					self.holdForLaterWave(message, 3, (self.num_nodes // 2 + 1) - self.brachaMsgCtrTotal[1][1 if msgValue else 0]) #second number is minimum number of messages needed before recheck 
				else:
					#...and we're not going to be able to hit it in this go-round.
					if debug_byz:
						print "Discarding unvalidateable wave 3 bracha message from {}, not enough wave 2 messages to validate {}.".format(message['sender'],msgValue)
					return
		
		
		
			
		#now check that we can actually store the messages	
		try:
			if self.brachabits[message['sender']][wave] is not None:
				if msgValue != self.brachabits[message['sender']][wave]:
					#wut-oh. In this case, there was a mismatch between a previous message we received and a current message - in the same wave. As in, that was already sent. This is indicative of a faulty node and earns the 
					if debug_byz:
							print "Received the same message with different values from node {}. This smells! Blacklisting.".format(message['sender'])
					blacklistNode(message['sender']) #remember, message['sender'] can't be forged. This property has to hold for this to work.
			else:
				self.brachabits[message['sender']][wave] = msgValue
				if self.brachabits[message['sender']][0]: #that is, if the node is deemed Good
					self.brachaMsgCtrGood[wave-1][1 if msgValue else 0] += 1
					if self.wave == 3:
						self.brachaMsgCtrGoodDeciding[1 if msgValue else 0] += 1
				self.brachaMsgCtrTotal[wave-1][1 if msgValue else 0] += 1 
				
				if self.wave == 1 and sum(self.brachaMsgCtrGood[0]) >= self.num_nodes - self.fault_bound:
					self.wave = 2
					self._brachaWaveTwo()
				if self.wave == 2:
					if sum(self.brachaMsgCtrGood[1]) >= self.num_nodes - self.fault_bound:
						self.wave = 3
						self._brachaWaveThree()
						
					checkHeldWaveMessages(2)
					#check wave messages
				if self.wave == 3:
					if sum(self.brachaMsgCtrGood[2]) >= self.num_nodes - self.fault_bound:
						self.wave = 4 #done with waves - mostly acts to prevent this from firing again
						self._brachaFinal()
				
					checkHeldWaveMessages(3)
					#check wave messages - happens after potential wave update to ensure quasi-atomicity
				
				#increment counters 
				#TODO: Release held stage 2 or 3 messages if we have enough stage 1/2 messages.
				#TODO: Call stage 2 or 3 if warranted.
					
		except KeyError:
			if debug_byz:
				print "Received a bracha message from a node I've never heard of: {}.".format(message['sender'])
			#IMPORTANT: so we have a specific defined behavior here: **We throw out the message.** This IS the flexible-node-list resilient behavior. Why? Because the node list is set at the start of the node opening the byzantine instance. If a new node is added to the global roster, it can jump in on new byzantine instances but not ones that are already in progress!
			return 
		
	def blacklistNode(sender):
		#TODO: implement this.
		#if we blacklist more than t nodes, we have a serious problem. What do we do then?
		#is it possible to blacklist ourselves?
		pass	
		
		#self.heldMessages = {'epoch':{}, 'iteration':{}, 'wave':{}}
		
	def holdForLaterEpoch(message, target_epoch):
		#saving a message until later. Fish saved messages out with checkHeldMessages.

		if target_epoch not in self.heldMessages['epoch']:
			self.heldMessages['epoch'][target_epoch] = blist()
		self.heldMessages['epoch'][target_epoch].append(message)
	
	def holdForLaterIteration(message, target_iter):
		#saving a message until later. Fish saved messages out with checkHeldMessages.

		if target_iter not in self.heldMessages['epoch']:
			self.heldMessages['epoch'][target_iter] = blist()
		self.heldMessages['iteration'][target_iter].append(message)
	
	def holdForLaterWave(message, wave, number_messages_needed):
		#saving a message until later. Fish saved messages out with checkHeldMessages.
		self.heldMessages['wave'][wave].add( (sum(self.brachaMsgCtrTotal[wave-1])+number_messages_needed, message) )
		#the 'number_messages_needed' at the front - this number will only go DOWN as we receive more wave2/wave3 messages. (this works because held wave messages are wiped at the start of a new iteration) So the list is sorted in reverse order of the number of messages needed, and when we get a new message we just have to check the number of messages received and we're fine.
		
		#so we're putting (total messages received so far) + (num messages needed) at the front of each message. And when (total messages received) is >= that number, you pop the message.
		
	
	def checkHeldEpochMessages(target_epoch):
		if target_epoch not in self.heldMessages['epoch']:
			return
			
		for message in self.heldMessages['epoch'][target_epoch]:
			self.validatebrachaMsg(message)
			#messages will never return here. They either go into the iteration or wave hold buckets, get processed, or get discarded.
		
		del self.heldMessages['epoch'][target_epoch]
		
	def checkHeldIterMessages(target_iter):
		if target_iter not in self.heldMessages['iteration']:
			return
			
		for message in self.heldMessages['iteration'][target_iter]:
			self.validatebrachaMsg(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['iteration'][target_iter]
	
	def checkHeldWaveMessages(wave): #check function signature of this
		#TODO: This doesn't work. Messages can get put back in the late-wave bucket because the number of messages needed is just a minimum.
		while len(self.heldMessages['wave'][wave]) > 0:
			if self.heldMessages['wave'][wave][-1][0] <= sum(self.brachaMsgCtrTotal[wave-1]:
				#this pulls out the message with the lowest # of messages (0) stored for the current wave held list (self.heldMessages['wave'][wave]) and checks its message counter [0] to see if we've received that many messages of the previous wave. If so, we reprocess it and repeat.
				message = self.heldMessages['wave'][wave].pop(0)[1]
				self.validatebrachaMsg(message)
			else:
				#otherwise, we end this while loop.
				break	
			
		
		#we can shortcut a lot of this by considering reasons messages are held:
		#future epoch
			#refresh: on new epoch (can check by number)
		#future iteration
			#refresh: on new iteration (ditto)
		#wave with not enough validated messages to pass on
			#refresh: on receiving a new message of the previous wave, or at least enough messages of the previous wave
		#This function goes through the message held list in order and feeds it to the validator one by one. We stop when we reach where the end of the message held list was when we started. Then we take only the new bit and it becomes the held messages queue.

	
		
	def clearHeldEpochMessages():
		#called on reset. 
		self.heldMessages['epoch'] = {}
		
	def clearHeldIterMessages():
		#called on new epoch. 
		self.heldMessages['wave'] = {}
		
	def clearHeldWaveMessages():
		#called on new iteration. 
		self.heldMessages['wave'] = {2:sortedlist(key=lambda x: x[0]), 3:sortedlist(key=lambda x: x[0])}
		
	
	def _brachaWaveTwo():
		if self.brachaMsgCtrGood[0][0] > self.brachaMsgCtrGood[0][1]:
			self.value = (False,)
		if self.brachaMsgCtrGood[0][0] < self.brachaMsgCtrGood[0][1]:
			self.value = (True,)
		#if they are equal, we stay where we are.
		
		#Bracha Wave 2
		ReliableBroadcast.broadcast((MessageMode.bracha, 2, self.value),extraMeta=(self.ID,self.epoch,self.iteration)):
		#also, count myself (free).
		self.brachabits['username'][2] = self.value
		
		if self.brachabits['username'][0]: #if we're a good node:
			self.brachaMsgCtrGood[1][1 if self.value[0] else 0] += 1
		self.brachaMsgCtrTotal[1][1 if self.value[0] else 0] += 1
		#TODO: IMPORTANT - Broadcast SHOULD loop back, but if it does not, we need to call ValidateMessage manually. This could the last received message needed to advance to another wave...!
		
	
	def _brachaWaveThree():
		if self.brachaMsgCtrGood[0][0] > self.num_nodes // 2:
			self.value = (False,True) #decide
		elif self.brachaMsgCtrGood[0][1] > self.num_nodes // 2:
			self.value = (True,True) #decide
		else:
			self.value = (self.value[0],False) #no decide
		
		#Bracha Wave 2
		ReliableBroadcast.broadcast((MessageMode.bracha, 3, self.value),extraMeta=(self.ID,self.epoch,self.iteration)):
		#also, count myself (free).
		self.brachabits['username'][3] = self.value[0]

		if self.brachabits['username'][0]: #if we're a good node:
			self.brachaMsgCtrGood[2][1 if self.value[0] else 0] += 1
			if self.value[1]:
				self.brachaMsgCtrGoodDeciding[1 if self.value[0] else 0] += 1
		self.brachaMsgCtrTotal[2][1 if self.value else 0] += 1
		
	
	def _brachaFinal():
		#find maximum number of decider messages. Is it 0 or 1?
		num_deciding_messages = max(self.brachaMsgCtrGoodDeciding)
		deciding_value = self.brachaMsgCtrGoodDeciding.index(num_deciding_messages)
		deciding_equal = (self.brachaMsgCtrGoodDeciding[0] == self.brachaMsgCtrGoodDeciding[1])
	
		if num_deciding_messages >= self.num_nodes - self.fault_bound:
			self.decided = True
			self.decision = True if deciding_value == 1 else False
			
			
			return
		elif num_deciding_messages > self.fault_bound:
			self.globalCoin()
			if not deciding_equal:
				self.value = (True if deciding_value == 1 else False,)
			else:
				self.value = (self.value[0],) #tie result, value carries over
			#run coin, discard value, new iteration
			self.iteration += 1
			self._startBracha()
		else: 
			self.value = (self.globalCoin(),)
			#run coin, set value, cycle
			self.iteration += 1
			self._startBracha()
			
		
	
		
def getAllNodes():
	#and here we end up with another pickle: for byzantine agreement to WORK, every node needs to know how many other nodes there are and what they are called.
	#the instance also needs its node list to stay stable for the term of agreement. Nodes can't join in the middle of an agreement instance!
	#this is the answer. When called, it gives the node list AT THE TIME OF THE CALL. Then that sticks to the instance object thereafter.
	
	#MODULAR - this function is modular and is expected to be swapped out given whatever's your requirements.
	pass
	#TODO - this function also needs to be completed, too.

def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	print "Starting up..."
	global username, num_nodes, fault_bound
	username = args[0]
	MessageHandler.init(username,"node")
	num_nodes = int(args[1])
	fault_bound = num_nodes // 3 - 1 if num_nodes % 3 == 0 else num_nodes // 3 #t < n/3. Not <=.
	print "Maximum adversarial nodes: {}/{}.".format(fault_bound, num_nodes)
	weSaidNoMessages = False 
	while True:
		#print "Checking for messages."
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
					ReliableBroadcast.broadcast(message['body']])
				elif code == "byzantine":
					#a conundrum. How do nodes AGREE to start a byzantine agreement instance?
					#for the time being, the client notifies every node and gives them an initial value - ideal for testing.
					#in a real world distributed system, this would be through some other kind of context.
					byzID = message['meta']['byzID'] #byzantine instance ID
					byzValue = message['body'][1] #starting value
					ByzantineAgreement.new(byzID, byzValue)
				
				else:
					print "Unknown client message received - code: {}.".format(message['meta']['code'])
					print repr(message)
					pass #no other types of client messages implemented yet.
			
			elif message['type'] == "node":
				#reliable broadcast message format: 
				#metadata has type.
				msgType = msgBody[0]
				if msgType == "rBroadcast":
					result = ReliableBroadcast.handleRBroadcast(message)
					if result is not None:
						#result from Accept. Do stuff.
						print "Accepted message: "+repr(result)
				else:
					print "Unknown node message received."
					print message.headers
					print message.body
					pass #TODO: throw error on junk message. Or just drop it.
			elif type == "announce":
				#announce to client - IGNORE
				pass
			else: 
				print "Unknown message received."
				print message.headers
				print message.body
				pass #malformed headers! Throw an error? Drop? Request resend?
				
			
				

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