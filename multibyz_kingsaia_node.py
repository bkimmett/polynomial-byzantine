#!/usr/bin/env python

from __future__ import division
from sys import argv, exit
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


#Reminder: message[sender] is the node that sent the message the 'last mile'. rbid[0] is the real originating sender.

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
	def handleRBroadcast(thisClass,message,checkCoinboardMessages=True): #when a coinboard message is released from being held, the release function will call handleRBroadcast but set the extra argument to false. This skips having it checked again. Everyone else: don't use this argument for anything.
		
		#new message format = 
		
		#{'body': message.decode(), 'type': message.headers.type, 'sender': message.headers.sender, 'meta': message.headers.meta}
		
		#meta format: {'phase':RBPhase.initial,'rbid':(username,message_counter,extraMeta)}
				
		#TODO: Put 'try' blocks in here in case of malformed data (no rbid, no meta, bad meta, etc)			
		
		sender = message['sender'] #error?: malformed data
		data = message['body'] #first var is used for type, skip that  #, debuginfo
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
		
		
		try:
			if checkCoinboardMessages and type(data[0]) is ByzantineAgreement.MessageMode and (data[0] == ByzantineAgreement.MessageMode.coin_flip or data[0] == ByzantineAgreement.MessageMode.coin_list):
				instance = ByzantineAgreement.getInstance(rbid[2][0]) #rbid[2][0] = extraMeta[0] = byzID
				if not instance.checkCoinboardMessageHolding(message):
					return #if held, stop processing for now
				#coinboard message - possibly hold for later!
				#coinboard messages can be held for the following reasons:
				#GENERATE phase: IF j' (orig. sender) is not me AND message i' (flip#) > 1 AND I haven't received (n-t) acknowledgements for the message of (i'-1,j').
					#release held when: we receive enough acknowledgements for any message() in the coinboard not from us.
				#RESOLVE phase:	IF the list of j' has messages on it that I have not received. 
					#release held when: we receive all messages on that list. We might want to have 'check milestones' for the biggest number of remaining messages in a list, though even then lists might cycle on the hold list a few times.
				
				#TODO: As a check uses i' and j' (part of the message body), this means coinboard messages need to be verified before they are accepted. WELL before.
				#but it means coinboard messages can be accepted without verification (because they already have been). Double-edged sword.
				#TODO: Of course, we validate anyway. And we'll do a secondary message hold when coinboard messages are accepted, because we can still get ones from early/late epochs/iterations. 
		except Exception as err:
			print err
		
		
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
		self.heldMessages = {'epoch':{}, 'iteration':{}, 'wave':{2:sortedlist(key=lambda x: x[0]), 3:sortedlist(key=lambda x: x[0])}, 'coin_epoch':{}, 'coin_epoch_accepted':{}, 'coin_iteration':{}, 'coin_iteration_accepted':{}, 'coin_flip':{}, 'coin_list':{}}
		
		self.decided = False
		self.decision = None
		self.useCoinValue = False
		
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
		
		#TODO: Coinboards (but not past coinboards) should be reset on new Iteration.
		#TODO: Check coin messages at appropriate moments!!
		
		self.pastCoinboards = {}
		self.coinboard = [] #erase coin records
		self.whitelistedCoinboardList = set()
		self.knownCoinboardList = set()
		#TODO: reset these two lists each iteration...
		
		#self.pastWhitelistedCoinboardLists = {} #dictionary of sets - do we need this?
		
		self.coinColumnsReady = 0 #how many columns have been received by at least n-t nodes?
		self.precessCoin = False #if we're in coinState 0, do we move to coinState 2 immediately after coinState 1?
		self.lastCoinBroadcast = 0 #what's the last message_i (of our own) we broadcast?
		#TODO: Reset this whenever new coinboard.
		self.coinState = 0 
		#0 = coinboard not yet running
		#1 = coinboard running in 'generate' phase
		#2 = coinboard running in 'reconcile' phase
		#3 = coinboard is over
		#TODO: Also reset THIS at iteration with the board.
		
		#COINBOARD FORMAT:
		#array of x dicts. (where x is as in x-sync - number of rounds.) Dict #i  is for round i.
		#in each dict, keys are the j' s (usernames of nodes).
		#each value is a tuple: (value, acks)
		#where acks is a set() of who acks have been received from for this message.
		
		#past coinboards are stored by a tuple of (epoch,iteration).
		
		#a few notes on how the byzantine algorithm works and using fake multithreading
		#(aka 'event-driven programming')...
		#Start Epoch starts Bracha.
		#Bracha broadcasts the first wave and RETURNS until enough Wave 1 messages are validated.
		#then we set the byzValue and broadcast the second wave... yeah.
		#receiving bracha broadcast messages acts as a handler. 
		#this handler will trigger bracha next wave if necessary.
	
	def _startEpoch(self):
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
		
	def _startBracha(self):
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
		self.brachabits[username][1] = self.value
		if self.brachabits[username][0]: #if we're a good node:
			self.brachaMsgCtrGood[0][1 if self.value else 0] += 1
		self.brachaMsgCtrTotal[0][1 if self.value else 0] += 1
		
		#after we send our own message, we might as well check to see if there's any messages waiting.
		if self.iteration == 1:
			self.checkHeldEpochMessages(self.epoch)
		else:
			self.checkHeldIterMessages(self.iteration)
		self.wave = 1
		self.clearHeldWaveMessages()
		
		
	def validateBrachaMsg(self,message):	
		if self.decided: #inactive after decision
			return 
		#TODO: Better validation of bracha-style messages.
		try:
			extraMeta = message['meta']['rbid'][2]
			remoteByzID = extraMeta[0]
			if self.ID != remoteByzID:
				if debug_byz:
					print "Throwing out bracha message from {} with wrong Byzantine ID {} vs {}.".format(rbid[0],remoteByzID,self.ID)
					print "You should probably check your message routing. This isn't supposed to happen."
				return #throw out message. Somehow it was sent to the wrong iteration of byzantine agreement. How did this even happen?
			
			##Check Epoch
			epoch = int(extraMeta[1])
			if epoch < self.epoch:
				if debug_byz:
					print "Throwing out old bracha message from {}, epoch {} vs {}.".format(rbid[0],epoch,self.epoch)
				return #throw out message - it's old and can't be used
			if epoch > self.epoch:
				if debug_byz:
					print "Holding too-new bracha message from {}, epoch {} vs {}.".format(rbid[0],epoch,self.epoch)
				self.holdForLaterEpoch(message)
				return #this message can't be processed yet, it's from a different epoch entirely
			
			##Check Iteration
			iteration = int(extraMeta[2])
			if iteration > self.maxIterations:
				#a note about this part: one of the flaws in byzantine agreement is it assumes EVERY NODE KNOWS HOW MANY NODES THERE ARE AND WHO THEY ARE. If you're gonna add nodes to the network in real time you're probably going to have to do it BY byzantine agreement or a trusted third party, and then it'll take some nontrivial management to make sure enough nodes' node lists stay synchronized.
				#one thing this code DOES NOT ACCOUNT FOR is how to handle the effects of nodes joining and leaving in a resilient manner. As the classic textbook line goes, this is "left to the reader as an exercise". Sorry!
				#the reason I'm mentioning this here is that one of the reasons the below scenario can take place is that some nodes got the memo about a new node joining when this agreement instance started - and some (this one!) didn't.
				if debug_byz:
					print "Throwing out impossible bracha message from {}, iteration {} (max {}).".format(rbid[0],iteration,self.maxIterations)
					print "This can indicate a fault or nodes that are not uniformly configured with a maximum iteration limit (or nodes that have a different node list than this node at the start of the byzantine bit)."
				return #this can't be processed, it's from an iteration that's not supposed to happen.
			if iteration > self.iteration:
				if debug_byz:
					print "Holding too-new bracha message from {}, iteration {} vs {}.".format(rbid[0],iteration,self.iteration)
				self.holdForLaterIteration(message)
				return #this message can't be processed yet, maybe next (or some later) iteration
			if iteration < self.iteration:
				if debug_byz:
					print "Throwing out old bracha message from {}, iteration {} vs {}.".format(rbid[0],iteration,self.iteration)
				return #this message is from a past iteration that already concluded and is thus stale.
			
			##Check Wave
			wave = int(message['body'][1])
			if wave != 1 and wave != 2 and wave != 3:
				if debug_byz:
					print "Throwing out impossible bracha message from {} via {}, invalid wave {}.".format(rbid[0],message['sender'],wave)
				return #wave can only be one, two, or three. period.
			
			msgValue = message['body'][2]
			if not isinstance(msgValue, tuple) or (length(msgValue) not in [1,2]) or not all(type(item) is bool for item in items):
				#must be a tuple of 1 or 2 items. First item is value. Second item is wave 3 'decide' flag. Decide flag is ignored if it's a wave1/wave2 message.
				if debug_byz:
					print "Throwing out impossible bracha message from {} via {}, invalid message type {}.".format(rbid[0],message['sender'],type(msgValue))
				return
			
		except TypeError, ValueError, IndexError:
			if debug_byz:
				print "Value error. Message from {} via {} had to be discarded.".format(rbid[0],message['sender'])
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
						print "Holding uncertain wave 2 bracha message from {}, might not have enough wave 1 messages to validate {}.".format(rbid[0],msgValue)
					self.holdForLaterWave(message, 2, self.initial_validation_bound - self.brachaMsgCtrTotal[0][1 if msgValue else 0])
				else:
					#...and we're not going to be able to hit it in this go-round.
					if debug_byz:
						print "Discarding unvalidateable wave 2 bracha message from {}, not enough wave 1 messages to validate {}.".format(rbid[0],msgValue)
					return
				
				
			#wave 2 messages are valid IF we received at least n - t wave 1 messages (from any nodes) AND a majority of those n - t is for the value listed in the wave 2 message.
			#this is complicated somewhat by the fact that n - t >= 2t + 1. So the number of values we need for a 'majority' is actually (n - t) // 2 + 1. Or, about t+1. So it's possible for enough wave 1 messages to come in that wave 2 messages taking either position are viable.
		elif wave == 3:
			#wave 3 messages are more straightforward to validate - more than half of the nodes have to have settled to a pattern. This is quite unequivocal. 
			if not msgDecide:
				if msgValue != self.brachabits[rbid[0]][2] or self.brachaMsgCtrTotal[1][1 if msgValue else 0] >= self.num_nodes // 2 + self.fault_bound + 1:
					#basically, if 'decide' is false, two things must be true:
					#1. The node must have the same value as its Wave 2 message.
					#2A. There must not be more than n//2 + t nodes that have a specific value in their wave 2 message, as if there were, such a hypermajority would force the node to set 'decide' to true and their value to that value.
					#2B. This second condition is hard to hit as it requires this node receive more than n - t messages, but I'm including it just in case as it is a condition to check for.
					if debug_byz:
						print "Discarding unvalidateable wave 3 bracha message from {}, sender is not deciding and {} {}.".format(rbid[0], "changed value to" if msgValue != self.brachabits[rbid[0]][2] else "would be forced to decide", msgValue)
					#TODO: Maybe blacklist here?
					return
			
			if msgDecide and self.brachaMsgCtrTotal[1][1 if msgValue else 0] <= self.num_nodes // 2:
				#message isn't valid - we haven't received enough appropriate wave 2 messages.
				#we hold the message if there is the *potential* for there to be enough wave 1 messages. Otherwise we throw it out.
				if self.num_nodes - sum(self.brachaMsgCtrTotal[1]) + self.brachaMsgCtrTotal[1][1 if msgValue else 0] > self.num_nodes // 2:
					#...but we COULD hit it later.
					if debug_byz:
						print "Holding uncertain wave 3 bracha message from {}, might not have enough wave 2 messages to validate {}.".format(rbid[0],msgValue)
					self.holdForLaterWave(message, 3, (self.num_nodes // 2 + 1) - self.brachaMsgCtrTotal[1][1 if msgValue else 0]) #second number is minimum number of messages needed before recheck 
				else:
					#...and we're not going to be able to hit it in this go-round.
					if debug_byz:
						print "Discarding unvalidateable wave 3 bracha message from {}, not enough wave 2 messages to validate {}.".format(rbid[0],msgValue)
					return
		
		
		
			
		#now check that we can actually store the messages	
		
		#TODO: Switch check vs self.nodes to up here instead of relying on a try. Keep the try anyway.
		
		try:
			if self.brachabits[rbid[0]][wave] is not None:
				if msgValue != self.brachabits[rbid[0]][wave]:
					#wut-oh. In this case, there was a mismatch between a previous message we received and a current message - in the same wave. As in, that was already sent. This is indicative of a faulty node and earns the 
					if debug_byz:
							print "Received the same message with different values from node {}. This smells! Blacklisting.".format(rbid[0])
					blacklistNode(rbid[0]) #remember, a reliable broadcast sender (rbid[0]) can't be forged because it has to match the initial sender of the message, and THAT can't be forged. This property has to hold for this to work.
			else:
				self.brachabits[rbid[0]][wave] = msgValue
				if self.brachabits[rbid[0]][0]: #that is, if the node is deemed Good
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
				print "Received a bracha message from a node I've never heard of: {} via {}.".format(rbid[0], message['sender'])
			#IMPORTANT: so we have a specific defined behavior here: **We throw out the message.** This IS the flexible-node-list resilient behavior. Why? Because the node list is set at the start of the node opening the byzantine instance. If a new node is added to the global roster, it can jump in on new byzantine instances but not ones that are already in progress!
			return 
		
		
	def validateCoinMsg(self.message):
		#we still accept coinboard messages after decision... right?
		
		try: 
			#this first bit is just about the same as bracha: epoch and iteration-
			#-except we don't throw out old coin messages. We process them like all others.		
			#this variable determines whether it's an old coin message or not.
			message_from_the_past = False
			
			##Check Epoch
			epoch = int(extraMeta[1])
			if epoch < self.epoch:
				message_from_the_past = True
			if epoch > self.epoch:
				if debug_byz:
					print "Holding too-new coin message from {}, epoch {} vs {}.".format(rbid[0],epoch,self.epoch)
				self.holdAcceptedCoinForLaterEpoch(message,epoch)
				return #this message can't be processed yet, it's from a different epoch entirely
			
			##Check Iteration
			iteration = int(extraMeta[2])
			if iteration > self.maxIterations:
				
				if debug_byz:
					print "Throwing out impossible coin message from {}, iteration {} (max {}).".format(rbid[0],iteration,self.maxIterations)
					print "This can indicate a fault or nodes that are not uniformly configured with a maximum iteration limit (or nodes that have a different node list than this node at the start of the byzantine bit)."
				return #this can't be processed, it's from an iteration that's not supposed to happen.
			if iteration > self.iteration:
				if debug_byz:
					print "Holding too-new coin message from {}, iteration {} vs {}.".format(rbid[0],iteration,self.iteration)
				self.holdAcceptedCoinForLaterIteration(message,iteration)
				return #this message can't be processed yet, maybe next (or some later) iteration
			if iteration < self.iteration:
				message_from_the_past = True
			
			## Check data integrity
			data = message['body']
			mode = data[0]
			
			if(type(mode) is not MessageMode):
				if debug_byz:
					print "Throwing out not-a-coin message from {} via {} (real type {}).".format(rbid[0],message['sender'],type(mode))
					print "This is NOT supposed to happen - noncoin messages aren't even supposed to hit this function. Debug time!"
				return #this can't be processed, no way no how.
					
		except Exception as err:
			print err 
			raise err
			#TODO: build a better exception handler and handle errors properly
			
		if rbid[0] not in self.nodes or message['sender'] not in self.nodes:
			if debug_byz:
				print "Who sent this? Received a coin message from/via a node {} via {} we don't know.".format(rbid[0], message['sender'])
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
			except Exception as err:
				print err 
				raise err
				#TODO: build a better exception handler and handle errors properly
		
			if type(message_i) is not int:
				if debug_byz:
					print "Invalid coinflip message from {} via {}, sync round# type {} instead of integer.".format(rbid[0],message['sender'],type(message_i))
				return
		
			if message_i < 1: #TODO: or message_i > ???
				if debug_byz:
					print "Invalid coinflip message from {} via {}, impossible round# ().".format(rbid[0], message['sender'],message_i)
				return
		
			if message_j not in self.nodes:
				#By the way: there's probably a line to be had here about untrusted data, but we're assuming adversaries WILL NOT try to induce arbitrary code execution with node IDs, or anything else. 
				#if you are reading this, and you're implementing this on a production system, you had better sanitize your inputs and add whatever else security you think is necessary, 'k? I did my best, but there's no WAY I thought of everything.
				if debug_byz:
					print "Received a coin message about a node {} we don't know.".format(message_j)
				return
		
			if mode == MessageMode.coin_flip and type(message_value) is not bool:
				if debug_byz:
					print "Invalid coinflip message from {} via {}, message type {} instead of boolean.".format(rbid[0],message['sender'],type(message_value))
				return

			if message_from_the_past:
				if (epoch,iteration) not in self.pastCoinboards:
					#we don't have ANY coinboard records from back then. How'd that happen? 
					if debug_byz:
						print "Warning: had to generate a new past coinboard for old epoch/iter {}/{}.".format(epoch,iteration)
					#generate a new coinboard on the spot.
					self.pastCoinboards[(epoch,iteration)] = [{} for x in range(self.num_nodes)]
					
				this_coinboard = self.pastCoinboards[(epoch,iteration)]
			else:
				this_coinboard = self.coinboard
				
			while len(this_coinboard) < self.num_nodes:
				this_coinboard.append({}) #add blank extra spaces to fill out board
			if message_j not in this_coinboard[message_i]:
				this_coinboard[message_i][message] = (None,set()) #setup record
			
			##OK, we've done some light validation, now store it.
			
			if mode == MessageMode.coin_flip:
				if message_j != rbid[0]: #sender doesn't match who the message is about, i.e. this is a forgery or a screw-up of grand proportions
					if debug_byz:
						print "{} tried to forge {}'s coin flip message. Discarding/blacklisting.".format(rbid[0],message_j)
					self.blacklistNode(rbid[0])
					return
			
				if this_coinboard[message_i][message_j][0] is None:
					#no value stored
					this_coinboard[message_i][message_j][0] = message_value
					#TODO: check coin list messages here.
					#checkHeldCoinListMessage()
					
					if not message_from_the_past and self.coinState < 2:
						self._acknowledgeCoin(message_i,message_j)
						#Broadcast acknowledgement that we received this message - but only if this is the current coinboard and we haven't sent our own list yet.
						
				else:
					if message_value != this_coinboard[message_i][message_j][0]:
						#We have two messages with different values? This isn't supposed to happen. Blacklist the node...
						if debug_byz:
							print "{} sent the same flip twice, with two different values. Discarding/blacklisting.".format(rbid[0])
						self.blacklistNode(rbid[0])
						
						return
						
			
			if mode == MessageMode.coin_ack:
				this_coinboard[message_i][message_j][1].append(rbid[0]) #sender of broadcast
				#Check number of acknowledgements.
				if this_coinboard[message_i][message_j][1] == self.num_nodes-self.fault_bound:
					#we've hit the boundary number of acknowledgements! (n-t)
					#we trigger this only once - it does thing like continue the state.				
					#we also (if we're in Stage 1) need to check for the number of acknowledgements - if we get enough columns, we move on to stage 2. (If we're in Stage 0, we store that we're ready to move on until Stage 1...)
					if not message_from_the_past and self.coinState < 2:
						if message_i == self.num_nodes - 1: 
							self.coinColumnsReady += 1
							if self.coinColumnsReady == self.num_nodes - self.fault_bound:
								if self.coinState == 1:
									self.coinState = 2
									self._broadcastCoinList()
								else:
									self.precessCoin = True
								#move to state 2... or at least say we're ready to do so	
					
					if message_j == username:
						#if we reach the set number for our flip, broadcast the next flip.
						if not message_from_the_past:	
							#this does assume it's OUR flip NOW, mind you. If we've gotten all the acknowledgements finally for an old coinboard, then the decision is already made and there's no point updating it further.				
							if message_i != self.lastCoinBroadcast:
								if debug_byz:
									print "SERIOUS ERROR: OK, so we received the correct number of acknowledgements for one of our {} coin flips, and not the one we just broadcast (currently {} vs {} received). This SHOULD be completely impossible without time travel, glitch, or forgery on a grand scale. ".format("earlier" if message_i < self.coinBroadcast else "later",self.lastCoinBroadcast,message_i)
								#TODO: But do we DO anything about it?
							else:
								self.lastCoinBroadcast += 1
								if self.lastCoinBroadcast < self.num_nodes:
									coin = self._broadcastCoin(self.lastCoinBroadcast)
									##TODO: This can never happen while the coinboard is undefined, right?
									self.coinboard[self.lastCoinBroadcast][username] = [coin,set()] #TODO: Should this be a sortedset()?
									#this will overwrite any acks that were already there, but... yeah, how could acks arrive if the coin hadn't been broadcast yet?! Not a concern.		
									self.coinboard[self.lastCoinBroadcast][username][1].append(username) #acknowledge receipt of our own message.
					else:
						#if we reach the set number for someone else's flip, release reliable broadcast for the next in the series, if it exists.
						#we do this EVEN IN THE CASE OF IT BEING IN THE PAST.
						checkHeldCoinFlipMessages(message_i, message_j, searchEpoch=epoch, searchIteration=iteration)
					
				
				#a question: do we always broadcast next flip FIRST or check for while loop first?
				#probably check for while loop. broadcast next flip could also be checking held flip messages, so a lot of released messages that way. Do releases after state updates.

		
		elif mode == MessageMode.coin_list:
			if message_from_the_past:
				if debug_byz: 
					print "Throwing out old coin list message (e/i {}/{}) from {}.".format(epoch,iteration,rbid[0])
				#old coin list messages have no use.
				return
			
			
			try:
				coin_list = data[1]
			except Exception as err:
				print err
				raise
				#TODO: build better exception handler.
			
			#if rbid[0] in self.whitelistedCoinboardList:
			#	return
				#duplicate coin list - we can skip this as it's already been validated.
			
			if rbid[0] in self.knownCoinboardList:
				return
				#duplicate coin list - we can skip this as it's already been received.
				#we don't need the whitelist above as this will be a superset of it.
				
			self.knownCoinboardList.append(rbid[0]) #we've received this list!
			
			list_looks_OK = True
			
			try: 
				for node in coin_list: #expecting list of [name,highest_i] values
					highest_i = node[1]
					if self.coinboard[highest_i][node[0]][0] is None:
						list_looks_OK = False #empty slot? throw out
					#this can also fail and fall through to the except, of course.
			except KeyError,ValueError,IndexError:
				list_looks_OK = False #the list referenced a node or whatever that our coinboard doesn't have.
				#this also takes care of invalid I and J errors; the coin list will just be held forever until the new iteration starts, then it get thrown out.
			
			if list_looks_OK:
				self.whitelistedCoinboardList.append(rbid[0]) #sender node name
			
				if len(self.whitelistedCoinboardList) == self.num_nodes-self.fault_bound:
					#OK, it's go time! Move to stage 3.
					self.coinState = 3
					self._finalizeCoinboard() ##TODO
			else:
				self.holdCoinListForLater(coin_list)
				#hold list for later
			
		else:
			if debug_byz:
				print "Throwing out bracha or some other type of noncoin message from {} via {}.".format(rbid[0], message['sender'])
				print "This is NOT supposed to happen - noncoin messages aren't even supposed to hit this function. Debug time!"
			return #this can't be processed, no way no how.
	
	
	def _broadcastCoin(self,message_i):
		global username, random_generator
		flip = (random_generator.random() >= .5) #True if >= .5, otherwise False. A coin toss.
		ReliableBroadcast.broadcast((MessageMode.coin_flip, message_i, username, ),extraMeta=(self.ID,self.epoch,self.iteration))
		
		return flip #so we can use it too
		
	def _acknowledgeCoin(self,message_i,message_j):
		ReliableBroadcast.broadcast((MessageMode.coin_ack, message_i, message_j),extraMeta=(self.ID,self.epoch,self.iteration))	
		
	
	def _finalizeCoinboard(self):
		pass
		#TODO: make this
		
	def _broadcastCoinList(self):
		pass
		#TODO: guess what: make this
		
	def blacklistNode(self,sender):
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
	
	def holdForLaterIteration(self,message, target_iter):
		#saving a message until later. Fish saved messages out with checkHeldMessages.

		if target_iter not in self.heldMessages['epoch']:
			self.heldMessages['epoch'][target_iter] = blist()
		self.heldMessages['iteration'][target_iter].append(message)
	
	def holdForLaterWave(message, wave, number_messages_needed):
		#saving a message until later. Fish saved messages out with checkHeldMessages.
		self.heldMessages['wave'][wave].add( (sum(self.brachaMsgCtrTotal[wave-1])+number_messages_needed, message) )
		#the 'number_messages_needed' at the front - this number will only go DOWN as we receive more wave2/wave3 messages. (this works because held wave messages are wiped at the start of a new iteration) So the list is sorted in reverse order of the number of messages needed, and when we get a new message we just have to check the number of messages received and we're fine.
		
		#so we're putting (total messages received so far) + (num messages needed) at the front of each message. And when (total messages received) is >= that number, you pop the message.
		
	def holdCoinForLaterEpoch(message,target_epoch):
		#We store coin messages separately from bracha messages because they are processed differently when fishing them out.	
		
		if target_epoch not in self.heldMessages['coin_epoch']:
			self.heldMessages['coin_epoch'][target_epoch] = blist()
		self.heldMessages['coin_epoch'][target_epoch].append(message)
		
	def holdAcceptedCoinForLaterEpoch(self,message,target_epoch):
		#We store coin messages separately from bracha messages because they are processed differently when fishing them out.	
		
		if target_epoch not in self.heldMessages['coin_epoch_accepted']:
			self.heldMessages['coin_epoch_accepted'][target_epoch] = blist()
		self.heldMessages['coin_epoch_accepted'][target_epoch].append(message)
		
	def holdCoinForLaterIteration(message,target_iter):
		if target_iter not in self.heldMessages['coin_iteration']:
			self.heldMessages['coin_iteration'][target_iter] = blist()
		self.heldMessages['coin_iteration'][target_iter].append(message)
		
	def holdAcceptedCoinForLaterIteration(message,target_iter):
		if target_iter not in self.heldMessages['coin_iteration_accepted']:
			self.heldMessages['coin_iteration_accepted'][target_iter] = blist()
		self.heldMessages['coin_iteration_accepted'][target_iter].append(message)
		
	def holdCoinForSufficientAcks(self,message,message_i,message_j):
		
		if (self.epoch,self.iteration) not in self.heldMessages['coin_flip']:
			self.heldMessages['coin_flip'][(self.epoch,self.iteration)] = {}
			
		
		if (message_i,message_j) not in self.heldMessages['coin_flip'][(self.epoch,self.iteration)]:
			self.heldMessages['coin_flip'][(self.epoch,self.iteration)][(message_i,message_j)] = blist()
		#multiple messages can be stored under the same i,j - reliable broadcast creates many copies!
		self.heldMessages['coin_flip'](self.epoch,self.iteration)][(message_i,message_j)].append(message)
		
	def holdCoinListForLater(message,list):
		stuff_to_fulfill = {}
		for coin_item in list:
			coin_j = coin_item[0]
			coin_i = int(coin_item[1])
			if coin_j not in self.nodes:
				if debug_byz:
					print "Not able to hold coin list from {}. It has a node {} we've never heard of that will never appear in our coinboard.".format(message['meta']['rbid'][0],coin_j)
				return
			if type(coin_i) is not int or coin_i < 0 or coin_i > self.num_nodes:
				if debug_byz:
					print "Not able to hold coin list from {}. It has an invalid i ({}) on {}'s column.".format(message['meta']['rbid'][0],coin_i,coin_j)
				return
			if coin_j in stuff_to_fulfill:
				if debug_byz:
					print "Warning: Coin list from {} may be invalid. It has more than one entry for j {}.".format(message['meta']['rbid'][0],coin_j)
				if coin_i <= stuff_to_fulfill[coin_j]:
					return #accept the higher of the two values in the duplicate
				
			if len(self.coinboard) < coin_i:
				stuff_to_fulfill[coin_j] = coin_i
				continue
			if coin_j not in self.coinboard[coin_i]:
				self.coinboard[coin_i][coin_j] = [None,set()] #set up coinboard entry for when it shows up
				stuff_to_fulfill[coin_j] = coin_i
				continue
			if self.coinboard[coin_i][coin_j][0] is None:
				stuff_to_fulfill[coin_j] = coin_i	
				
		if len(stuff_to_fulfill) == 0:
			if debug_byz:
					print "Why are we holding the coin list from {}? It appears to be up to date.".format(message['meta']['rbid'][0])
				
		self.heldMessages['list'].append([stuff_to_fulfill,message])
	
	def checkHeldEpochMessages(self,target_epoch):
		if target_epoch not in self.heldMessages['epoch']:
			return
			
		for message in self.heldMessages['epoch'][target_epoch]:
			self.validatebrachaMsg(message)
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
			self.validatebrachaMsg(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['iteration'][target_iter]
		
	def checkHeldCoinIterMessages(self, target_iter):
		if target_iter not in self.heldMessages['coin_iteration'] and target_iter not in self.heldMessages['coin_iteration_accepted']:
			return
			
		for message in self.heldMessages['coin_iteration'][target_iter]:
			if message['body'][0] == MessageMode.coin_ack:
				#Throw here - ack messages aren't supposed to be held here.
				#TODO: actually throw.
				continue
			
			ReliableBroadcast.handleRBroadcast(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['coin_iteration'][target_iter]
		
		for message in self.heldMessages['coin_iteration_accepted'][target_iter]:
			self.validateCoinMsg(message)
			#again, messages will never return here - same reason.
		
		del self.heldMessages['coin_iteration_accepted'][target_iter]
	
	def checkHeldWaveMessages(self, wave): #check function signature of this
		#TODO: This doesn't work. Messages can get put back in the late-wave bucket because the number of messages needed is just a minimum.
		#EDIT: This works now (probably) now that heldMessages['wave'] uses a sorted list.
		while len(self.heldMessages['wave'][wave]) > 0:
			if self.heldMessages['wave'][wave][-1][0] <= sum(self.brachaMsgCtrTotal[wave-1]):
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
	
	def checkHeldCoinFlipMessages(self, target_i,target_j,searchEpoch=self.epoch,searchIteration=self.iteration):
	#somewhat contrary to the name, this RELEASES held coin flip messages for the specific thing. 
	#it is only to be called if enough acknowledgements have been received for that reliable broadcast message to be participated in, as it bypasses reverification.
		if (searchEpoch,searchIteration) not in self.heldMessages['coin_flip']:
			return
		if (target_i,target_j) not in self.heldMessages['coin_flip'][(searchEpoch,searchIteration)]:
			return
			
		for message in self.heldMessages['coin_flip'][(searchEpoch,searchIteration)][(target_i,target_j)]:
			ReliableBroadcast.handleRBroadcast(message,checkCoinboardMessages=False)
		
		del self.heldMessages['coin_flip'][(searchEpoch,searchIteration)][(target_i,target_j)]
	
		
	def checkHeldCoinListMessages():
		pass
		###TODO: Yeah, sort this out
		
	
		
	def clearHeldEpochMessages():
		#called on reset. 
		self.heldMessages['epoch'] = {}
		self.heldMessages['coin_epoch'] = {}
		self.heldMessages['coin_epoch_accepted'] = {}
		
	def clearHeldIterMessages():
		#called on new epoch. 
		self.heldMessages['iteration'] = {}
		self.heldMessages['coin_iteration'] = {}
		self.heldMessages['coin_iteration_accepted'] = {}
		
	def clearHeldWaveMessages():
		#called on new iteration. 
		self.heldMessages['wave'] = {2:sortedlist(key=lambda x: x[0]), 3:sortedlist(key=lambda x: x[0])}
		
	#coinboard flip messages, and by extension, coinboard epoch/iteration messages, are NEVER cleared (the latter because flip and list messages are stored together in the epoch/iter buckets and we'd want to keep the flip messages). Even if a new iteration starts, old flips will be written into the coinboard to help along anyone else who comes calling.
	
	def clearHeldCoinListMessages():
		#called on new iteration - if a new iteration starts, we must have r-received n - t coin lists, NOT counting whatever is in here, so every other good node will receive same. (Or we're a bad node and it doesn't matter.)
		self.heldMessages['coin_list'] = {}
	
	
	def _brachaWaveTwo():
		if self.brachaMsgCtrGood[0][0] > self.brachaMsgCtrGood[0][1]:
			self.value = (False,)
		if self.brachaMsgCtrGood[0][0] < self.brachaMsgCtrGood[0][1]:
			self.value = (True,)
		#if they are equal, we stay where we are.
		
		#Bracha Wave 2
		ReliableBroadcast.broadcast((MessageMode.bracha, 2, self.value),extraMeta=(self.ID,self.epoch,self.iteration)):
		#also, count myself (free).
		self.brachabits[username][2] = self.value
		
		if self.brachabits[username][0]: #if we're a good node:
			self.brachaMsgCtrGood[1][1 if self.value[0] else 0] += 1
		self.brachaMsgCtrTotal[1][1 if self.value[0] else 0] += 1
		#TODO: IMPORTANT - Broadcast SHOULD loop back, but if it does not, we need to call ValidateMessage manually. This could the last received message needed to advance to another wave...!
		
	
	def _brachaWaveThree(self):
		if self.brachaMsgCtrGood[0][0] > self.num_nodes // 2:
			self.value = (False,True) #decide
		elif self.brachaMsgCtrGood[0][1] > self.num_nodes // 2:
			self.value = (True,True) #decide
		else:
			self.value = (self.value[0],False) #no decide
		
		#Bracha Wave 2
		ReliableBroadcast.broadcast((MessageMode.bracha, 3, self.value),extraMeta=(self.ID,self.epoch,self.iteration)):
		#also, count myself (free).
		self.brachabits[username][3] = self.value[0]

		if self.brachabits[username][0]: #if we're a good node:
			self.brachaMsgCtrGood[2][1 if self.value[0] else 0] += 1
			if self.value[1]:
				self.brachaMsgCtrGoodDeciding[1 if self.value[0] else 0] += 1
		self.brachaMsgCtrTotal[2][1 if self.value else 0] += 1
		
	
	def _brachaFinal(self):
		#brachaFinal only fires once - afterward the instance is in 'wave 4' until a new iteration starts.
		
		#find maximum number of decider messages. Is it 0 or 1 that takes the crown?
		num_deciding_messages = max(self.brachaMsgCtrGoodDeciding)
		deciding_value = self.brachaMsgCtrGoodDeciding.index(num_deciding_messages)
		deciding_equal = (self.brachaMsgCtrGoodDeciding[0] == self.brachaMsgCtrGoodDeciding[1])
	
		if num_deciding_messages >= self.num_nodes - self.fault_bound:
			self.decided = True
			self.decision = True if deciding_value == 1 else False
			
			
			return
		elif num_deciding_messages > self.fault_bound:
			#TODO: This is set up wrong. We need a new function that triggers the iteration if and only if the coinboard returns. Sorry guys.
			#what we CAN do here is set up a flag so that the value is set to be captured from globalCoin... or not.
			self.useCoinValue = False
			
			
			self.globalCoin()
			if not deciding_equal:
				self.value = (True if deciding_value == 1 else False,) #if it's a tie, we stay with our previous value.
			else:
				self.value = (self.value[0],) #tie result, value carries over
			#run coin, discard value, new iteration
			self.iteration += 1
			self._startBracha()
		else: 
			self.useCoinValue = True
		
			self.value = (self.globalCoin(),)
			#run coin, set value, cycle
			self.iteration += 1
			self._startBracha()
			
	
		
	def checkCoinboardMessageHolding(self,message):
		#this only checks and holds messages for coinboard reasons (i.e. not for epoch/iteration reasons. Mind you, any message held for epoch/iteration reasons could probably ALSO be held for coinboard reasons, so...)
		
		#reminder: rbid = sender, counter, extraMeta. 
		#extraMeta = byzID, epoch, iteration.
		#if self.decided: 
		#	return False #I've decided, I'm not accepting any more coinboard messages
		#TODO: Can I really include the above? I'm relying on Bracha's lemma which states that all good nodes agree this turn OR next turn OR all good nodes run global-coin - in which case if this decides, we don't 
			
		#since a coinboard instance is associated with a byzantine instance AND an epoch AND a specific iteration, we need epoch and iteration holds as well as the rbid interrupts.
		try:
			messageExtraMeta = message['meta']['rbid'][2]
			messageEpoch = messageExtraMeta[1]
			messageIteration = messageExtraMeta[2]
			messageCoinMode = message['body'][0]
			messageOrigSender = message['meta']['rbid'][0]
			if messageCoinMode == MessageMode.coin_flip:
				message_i = message['body'][1]
				message_j = message['body'][2]
			if messageCoinMode == MessageMode.coin_list:
				message_list = message['body'][1]
		except TypeError, ValueError, IndexError:
			if debug_byz:
				print "Value error. Reliable? message from {} via {} had to be discarded.".format(rbid[0], message['sender'])
			return False #TODO: Is 'discard' the best thing here?
		
		search_past = False
		
		
		if messageCoinMode == MessageMode.coin_flip:
			search_past = False
			if message_i == 1:
				return True #we always accept i' == 1 messages
			else: 
				if self.epoch > messageEpoch:
					search_past = True
					#early message - look up past 
				elif self.epoch < messageEpoch: 
					holdCoinForLaterEpoch(message,messageEpoch) #TODO: release at START of target epoch - coinboard might be set up early for this sort of thing.
					return False #we're done here
				else: #epochs match
					if self.iteration > messageIteration:
						search_past = True
					elif self.iteration < messageIteration:
						holdCoinForLaterIteration(message,messageEpoch) #TODO: again, release at START of target iteration.
						return False 
				try:
					if search_past:
						acks_count = len(self.pastCoinboards[(messageEpoch,messageIteration)][message_i][messageOrigSender][1])
					else:
						acks_count = len(self.coinboard[message_i][messageOrigSender][1])
				except Exception as err:
					print(err)
					#TODO: What kind of exceptions do we run into here?
					
				if acks_count >= self.num_nodes - self.fault_bound:
					#let it go through
					return True
				else: 
					holdCoinForSufficientAcks(message,message_i,message_j)
					return False
		elif messageCoinMode == MessageMode.coin_list:	
			search_past = False
			if self.epoch > messageEpoch:
				search_past = True
			elif self.epoch < messageEpoch:
				holdCoinForLaterEpoch(message,messageEpoch) #when messages are released they'll be run back through this so we can use the same hold for both.
				return False
			else: 
				if self.iteration > messageIteration:
					search_past = True
				elif self.iteration < messageIteration:
					holdCoinForLaterIteration(message,messageEpoch) #TODO: again, release at START of target iteration.
					return False
			try: 
				if search_past:
					result, differences = checkListVsCoinboard(message_list,self.pastCoinboards[(messageEpoch,messageIteration)])
				else:
					result, differences = checkListVsCoinboard(message_list,self.coinboard)
				if not result:
					holdCoinListForLater(message,message_list,differences)
				return result #passed? T/F
			except Exception as err:
				print(err)
				#TODO: What kind of exceptions do we run into here?
				
	
		
		
def getAllNodes():
	#and here we end up with another pickle: for byzantine agreement to WORK, every node needs to know how many other nodes there are and what they are called.
	#the instance also needs its node list to stay stable for the term of agreement. Nodes can't join in the middle of an agreement instance!
	#this is the answer. When called, it gives the node list AT THE TIME OF THE CALL. Then that sticks to the instance object thereafter.
	
	#MODULAR - this function is modular and is expected to be swapped out given whatever's your requirements.
	pass
	#TODO - this function also needs to be completed, too.

def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	#TODO: This code is really, really, REALLY stale by now.
	print "Starting up..."
	global username, num_nodes, fault_bound, random_generator
	try:
		random_generator = random.SystemRandom
	except:
		print "Couldn't initialize RNG. Check that your OS/device supports random.SystemRandom()."
		exit()
		
	
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
					
					#TODO: May have fluffed class instantiation.
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