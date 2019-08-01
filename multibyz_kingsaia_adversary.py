#!/usr/bin/env python

#It's a lot like a firewall with deep packet inspection, really. Except mean.

from __future__ import division #utility
import random					#for coin flips
from sys import argv, exit, stdout 		#utility
from time import sleep, strftime 	#to wait for messages, and for logging
#from math import floor, sqrt, log 			#utility
#from copy import deepcopy 		#utility
#import numpy as np 				#for matrix operations in _processEpoch
#from json import dumps			#for making UIDs good
import multibyz_kingsaia_network_adversary as MessageHandler 
#getting an error with the above line? 'pip install kombu'
#import collections				#for data type checking of messages
#from enum import Enum			#for reliable broadcast and byzantine message mode phasing
#getting an error with the above line? 'pip install enum34'
from blist import blist 		#containers that offer better performance when they get big. maybe unnecessary?
#getting an error with the above line? 'pip install blist'
from multibyz_kingsaia_node_adversary import MessageMode

# A NOTE ON HOW THE ADVERSARY IS SIMULATED

# All of the communications of the implementation use Reliable Broadcast. Which is remarkably difficult to interfere with... which is kind of the point. So, to simulate it, we have each node add an extra step before it accepts a Reliable Broadcast message.
# The extra step is: the node sends its ID, along with the message it was about to accept, to the simulated adversary. The simulated adversary can choose to return it now (indicating no delay), return it later (indicating delay), or change it (which means the adversary has taken over the original sender of the node and now can broadcast whatever it wants, but is pretending to be normal)


instances = {}
current_master_gameplan_bracha = None
current_master_gameplan_coin = None

default_target = False

all_nodes = []

known_bracha_gameplans = ['none','split_vote','split_hold','force_decide','shaker','lie_like_a_rug']
known_coin_gameplans = ['none','lie_like_a_rug','wedge','blast','wedge_blast']

debug = True

#SETUP:

# set up backchannel

# set up node list, alter quota

# We also need to have separate state tracking for each byzantine instance we know of

def log(message):
	if debug:
		print "ADV {} {}".format(strftime("%H:%M:%S"),message)
		stdout.flush() #force write


def maybe_setup_instance(byzID, target=default_target):	
	if byzID not in instances:
		setup_instance(byzID, all_nodes, target_value=target)	
	


def setup_instance(byzID, node_list, target_value=None):
	global instances
	instances[byzID] = {}
	instances[byzID]['ID'] = byzID
	instances[byzID]['iters_per_epoch'] = num_nodes * 2 #default iteration constant.
	instances[byzID]['fault_list'] = [] #list of nodes the adversary has overtaken in this instance
	instances[byzID]['gameplan'] = current_master_gameplan_bracha 			#adversarial gameplan (bracha)
	instances[byzID]['gameplan_coin'] = current_master_gameplan_coin 	#adversarial gameplan (global-coin)
	instances[byzID]['target_value'] = target_value
	instances[byzID]['held_messages'] = {'wave1_wait':[], 'timing_holds':[None,{},{},{}]} #storage
	instances[byzID]['epoch'] = {'bracha':{'value':0, 'timing':0}, 'coin':{'value':0, 'timing':0}}
	instances[byzID]['iteration'] = {'bracha':{'value':0, 'timing':0}, 'coin':{'value':0, 'timing':0}} #the adversary, because it has stalling decisions over the rest of the game, tracks these separately.
	#TODO: Iteration turnover.
	instances[byzID]['wave_one_bracha_values'] = [set(),set()] #state: used to keep track of the wave 1 bracha values.
	instances[byzID]['wave_two_messages_counted'] = 0
	instances[byzID]['wave_three_messages_counted'] = 0
	instances[byzID]['decide_messages_counted'] = 0
	instances[byzID]['timing_quotas'] = setup_quotas(instances[byzID]['gameplan'], node_list, target_value)
	
	
def setup_quotas(gameplan, node_list, target_value):
	quota_list = [None,None,None,None]
	
	if gameplan is None:
		return quota_list
	elif target_value is None:
		print "Error: Tried to set up quotas for a gameplan without a target value. Not using quotas."
		return quota_list
		
	#reminder:	[1 if target_value else 0] means you're storing the TARGET QUOTA.
	#			[0 if target_value else 1] means you're storing the NONTARGET QUOTA.		

	#quotas can be None (no quota), or a dict (quota for each node). Inside that dict, you have either a None (no quota for that node) or a list (quota of true, false messages).
	
	if gameplan == "force_decide":
		quota_list[1] = {}
		for node in node_list: 
			quota_list[1][node] = [minority_bound,num_nodes] if target_value else [num_nodes,minority_bound]
		return quota_list
		
	if gameplan == "split_vote":
		quota_list[1] = {}
		quota_list[2] = {}
		flip = target_value
		for node in node_list: 
			quota_list[2][node] = [num_nodes // 2, num_nodes // 2] #we won't get more than n/2 wave 2 messages of either type, so the deciding flag is never set
			quota_list[1][node] = [minority_bound,num_nodes] if flip else [num_nodes,minority_bound] #true flip yields 'True' wave 2 message - false flip yields 'False' wave 2 message - this ensures the wave 2 messages are split half and have and the wave 2 quota works
			flip  = not flip
		return quota_list	
		
	if gameplan == "split_hold":
		quota_list[1] = {}
		quota_list[2] = {}
		quota_list[3] = {}
		#the adversary needs two node populations of sizes 2t to pull this off. Let's randomize them - it'll make it easier to check that end-of-wave held message release is working properly. Also, it's something a real adversary might do to make it harder to be detected.
		wave_one_subsample = random.sample(node_list,max(2*fault_bound, num_nodes // 2 + 1)) #this population might be larger than 2t if t is small
		wave_two_subsample = random.sample(node_list,2*fault_bound) #this population is always 2t big. We don't want more nodes popping the decide flag.
		
		for node in node_list:
			if node in wave_one_subsample:
				quota_list[1][node] = [minority_bound,num_nodes] if target_value else [num_nodes,minority_bound] #ensure target value is emitted
			else:
				quota_list[1][node] = [num_nodes,minority_bound] if target_value else [minority_bound,num_nodes] #nontarget value is emitted
			
			#post wave 1: (assuming target is TRUE):
			#2t TRUE2, rest FALSE2
			#for smaller t's:
			#n/2+1 TRUE2, rest FALSE2
			
			if node in wave_two_subsample:
				quota_list[2][node] = [majority - (num_nodes // 2 + 1),num_nodes] if target_value else [num_nodes,majority - (num_nodes // 2 + 1)] #ensure target value is emitted (wave 2 ver) WITH deciding flag and our target value
				
			else:
				quota_list[2][node] = [num_nodes // 2, num_nodes // 2] 
				#ensure deciding flag IS NOT emitted. We don't care about the values that much.
				#this can't hang because the number of messages required to progress to the next stage will ALWAYS be less than the number the quota will allow, for t < n/3
				
				#see in mathematica:
#				 Block[{n = 10000},
# 				 Plot[{
# 				   n - t,
# 					Min[Floor[n/2], Max[2 t, Floor[n/2] + 1]] + 
# 					 Min[Floor[n/2], n - Max[2 t, Floor[n/2] + 1]]
# 				   }, {t, 1/3*n, 1}]]
		
			#post wave 2:
			#2t #, DECIDING
			#rest NOT DECIDING	
			
			quota_list[3][node] = [majority - (fault_bound + 1),fault_bound*2] 
			#wave 3 quotas are strange; instead of determining by value, [False,True]
			#they determine by the deciding flag being set to [False,True].
			#so here, we allow up to 2t deciding messages. 
			#We always want t+1 deciding messages or more. So we only allow (n-t) - (t+1) non-deciding messages, because that guarantees at least t+1 decidings get through.
		return quota_list

	#this function sets up the pass quotas for timing
	
	#WAVE 1 GAMEPLAN QUOTAS:
	
	#split_vote: for ONE HALF the nodes: ALL target, [t] nontarget. For THE OTHER HALF the nodes: [t] target, ALL nontarget. Hold the rest until wave 2 emitted. If there is an ODD NODE OUT: hold all until *iteration is over*.
	#split_hold: for [2T] the nodes: ALL target, [t] nontarget. For the other [T+1] nodes: [t] target, ALL nontarget. Hold the rest until wave 2 emitted.
	#force_decide: for EVERY node: ALL target, [t] nontarget, hold the rest until wave 2 emitted.
	#shaker: We don't need no stinkin' quotas!
	
	#WAVE 2 GAMEPLAN QUOTAS:
	
	#split_vote: No quota, but if there's still an ODD NODE OUT, hold all (wave 2 msgs) until iteration is over.
	#split_hold: for [2T] the nodes:  ALL target [at most 2T], [2t+1 - n/2+1] nontarget. We need at least n/2+1 target messages, but the way wave 1 was set up, we should have [2t] vs [t+1] anyway. It's just a matter of making sure they all show up. For the other [T+1] nodes: [t+1] nontarget, [t] target. 
	#force_decide: No quota.
	#shaker: See above.
	
	
	#WAVE 3 GAMEPLAN QUOTAS:
	
	#split_vote: No quota, even on any ODD NODE OUT.
	#split_hold: for EVERY node: ALL (target, decide) [there'll be at most [2T]], [1 (one)] *, nondecide. 
	#force_decide: No quota.
	#shaker: Still nothin'.
	
	#TODO: Nodes need to notify the adversary of when they have finished a bracha iteration, and how.
	
	#if we somehow got this far, do this as a last resort...
	return quota_list #will probably be all None
	
	
	
	
#main loop:
	#read next 'accept' message
	#apply rules:
	#let it PASS?
	#CHANGE it? (that will make the originating node one of the nodes that form our alter quota, as the adversary can 'take over' messages sent by no more than T nodes)
		#If the adversary changes a message, it has to change that message for everybody. Reliable broadcast.
		#If the adversary chooses to change a message, dropping that message IS one of the changes it can make, but again - that DOES count against the alter quota!
	#HOLD it?
	
	#and based on this message's arrival, do we want to RELEASE any held messages?
	
	
	
	
# THE ADVERSARY'S GUIDE TO STACKING THE VOTE

# Modified-Bracha

# PRECONDITION: At least one node needs to have a natural False to start. [for simplicity we're assuming True is the desired value and the adversary wants False]	
	# If this doesn't hold, lying with t nodes in the first wave will get you ignored, and lying with t nodes in the second and third wave will fail to validate.
		#todo: TEST NAIVE LYING
		
# Step 1: Take over # nodes and have them say 'False' in wave 1, so that a minimum of t + 1 nodes can say 'False'. If you want a mixed result, make sure at least t + 1 nodes naturally say 'True'.

# Step 2: If you want a node to say 'True' in wave 2, feed them t + 1 'True's' or more. If you want a node to say 'False' in wave 2, you

# From there:
# SPLIT VOTE (triggers coin flip and everyone takes its value): n/2 nodes say to 'True' in Wave 1, n/2 nodes say 'False'. In wave 2, no node changes its value or indicates deciding, so in wave 3 everyone flips global-coin.
	#If you have an extra node giving no even split, just hold the extra node indefinitely. 

# SPLIT VOTE WITH HOLD (triggers coin flip, some nodes don't take its value) : set n/2 +1 nodes to 'False' in wave 2 (we're assuming you want the 'False' nodes to hold value; otherwise do this many 'True')

# then make sure the nodes you want to hold (less than 2t) get enough 'False' wave 2s to send a deciding wave 3 message as 'False'. Then make sure the rest don't change their vote by ensuring they don't get a majority of votes. Then, have all the deciding messages get from point A to point B on the nodes you want to hold.

# FORCE DECIDE:	set all nodes to 'False' in wave 2 and sit back and watch the fireworks.

def get_message_ID(message):
	try:
		return message['meta']['rbid'][2][0] #byzID
	except Exception as err:
		print err
		raise err
		
def get_message_sender(message):
	try:
		return message['meta']['rbid'][0] #sender
	except Exception as err:
		print err
		raise err		
		
# def maybe_return_unchanged_message(message):
# 	uid = get_uid(message)
# 	if uid in instances[instance]['changed_messages']:
# 		#if we had already changed this message, then change it the same way.
# 		message['body'] = instances[instance]['changed_messages'][uid]
# 	else:
# 		#if not, then add it to the untouched queue.	
# 		instances[instance]['untouched_messages'].add(uid)
# 		
# 	return_message(message)
# 	

def return_timing_message(message, skip_log=False):
	#if not skip_log:
	#	log("{} Releasing wave {} timing message [{}] from {} to {}.".format(get_message_id(message),wave,message['body'],message['meta']['rbid'][0],sender))

	MessageHandler.sendAsAdversary(message['body'],message['meta'],message['sender'])
	
def return_value_message(message):
	MessageHandler.adversaryBroadcast(message['body'],message['meta'],sender=message['sender'])


def hold_message(message,key):
	instance = get_message_ID(message)
	maybe_setup_instance(instance)

	instances[instance]['held_messages'][key].append(message)	
	
def hold_message_timing(message,sender,wave):
	instance = get_message_ID(message)
	maybe_setup_instance(instance)

	log("[{}] Holding wave {} timing message [{}] from {} to {}.".format(instance,wave,message['body'],message['meta']['rbid'][0],sender))

	if sender not in instances[instance]['held_messages']['timing_holds'][wave]:
		instances[instance]['held_messages']['timing_holds'][wave][sender] = []
		
	instances[instance]['held_messages']['timing_holds'][wave][sender].append(message)
	
	
def release_messages(instance, key): #, message_processor):
	maybe_setup_instance(instance)

	temp_messages_bucket = instances[instance]['held_messages'][key] #copy messages into temp bucket
	instances[instance]['held_messages'][key] = [] #clear actual message bucket

	for message in temp_messages_bucket:
		#process each held message again
		#message_processor(message)
		process_message(message, reprocess=True)
		
	
	#clear messages
	
def node_is_overtaken(instance, nodename):
	return nodename in instances[instance]['fault_list']		
	
def maybe_overtake_node(instance, nodename):
	if node_is_overtaken(instance, nodename):
		return True #node's already overtaken

	if len(instances[instance]['fault_list']) < fault_bound:
		log("[{}] Overtaking node {}.".format(instance,nodename))
		instances[instance]['fault_list'].append(nodename) #node is now officially Adversarial	
		return True
	
	#otherwise...
	return False #we've taken over all the nodes we can

#def get_uid(message):
	#UID format used to store changed messages
#	return (dumps(rbid),message['raw'])
  
 
def bracha_or_coin(message):
	if message['body'][0] == MessageMode.bracha:
		return 'bracha'
	elif message['body'][0] == MessageMode.coin_flip or message['body'][0] == MessageMode.coin_list or message['body'][0] == MessageMode.coin_ack:
		return 'coin'
		
	return None #not a bracha/coin message

def iter_rollover(thisInstance, key1, key2):
	thisInstance['iteration'][key1][key2] += 1
	if thisInstance['iteration'][key1][key2] == thisInstance['iters_per_epoch']:
		thisInstance['epoch'][key1][key2] += 1
		thisInstance['iteration'][key1][key2] = 0 
	

def maybe_change_message(message, new_body, only_if_node_already_overtaken=False):
	#only_if_node_already_overtaken is normally FALSE, which means the adversary will try and take over a node that's not already taken over.
	#if it's set to true, messages will only be changed once a node is already registered as overtaken.
	instance = get_message_ID(message)
	target_node = get_message_sender(message)	

	if ( node_is_overtaken(instance, target_node) if only_if_node_already_overtaken else maybe_overtake_node(instance, target_node) ) :
		#node is already counted as overtaken, or we just subverted it. Change is OK.
		message['body'] = new_body
		return message, True
		
	
	#otherwise: node IS NOT counted as overtaken, and we can't/won't overtake it. Return message without changes.
	return message, False
			
			
def maybe_change_bracha_message(message, new_value):
	#wrapper to change bracha values
	updated_value = list(message['body'][2])
	updated_value[0] = new_value
	updated_body = message['body'][:] #copy
	updated_body[2] = tuple(updated_value)
				
	#altered_message, success = maybe_change_message(message, updated_body) #overwrite message, if possible				
	return maybe_change_message(message, updated_body) #overwrite message, if possible

def process_bracha_message_value(message,thisInstance): #rbid,thisInstance):
	##KNOWN GAMEPLANS: split_vote, split_hold, force_decide, shaker, lie_like_a_rug:
	##'split_hold' = arrange matters so that a global-coin flip happens, but some/all nodes (maybe justthe ones with the adv. target value) keep their value instead. 
	##'split_vote' = arrange matters so that a global-coin flip happens, and all nodes use the result of that.
	##'force_decide' = arrange matters so that every node pre-decides on the adversary's chosen value. No global-coin proc. 
	
		#the above three gameplans require at least one good node start with the adversary's target value.
		#split_vote (and maybe split_hold) requires that one good node start with EACH value!
		
	##'shaker' = screw with message timing, but not values. Random delays, baby!
	##'lie_like_a_rug' = Any adversarial node insists that the adversary's target value is ideal. Quite possibly unconvincing depending on how things stacked up.
	log("{} Received bracha value message {} from {}.".format(thisInstance['ID'],message['body'],message['sender']))
	
	if thisInstance['gameplan'] == 'shaker' or thisInstance['gameplan'] == None:
		log("Returning message - no changes with this gameplan.")
		return_value_message(message) #shaker doesn't alter message values, ever. It just messes with timing.
		return #we're done here
		
	if thisInstance['gameplan'] == 'lie_like_a_rug': #lie like a rug just changes EVERYTHING with no regard for the rest
		#adversary prepares fake message
		altered_message, changed = maybe_change_bracha_message(message, (False if value else True) if thisInstance['target_value'] is None else thisInstance['target_value'] ) #overwrite message, if possible. if we don't have a target, swap the bit of the message. If we do have a target, set the value to that.
		if changed:
			log("Changed message value to {}".format(altered_message['body'][2][0]))
		log("Returning message.")
		return_value_message(altered_message)
		return
		
	#figure out what wave it is
	wave = int(message['body'][1])
	value = message['body'][2][0]
	

	
	if wave == 1:
		thisInstance['wave_one_bracha_values'][1 if value else 0].add(message['sender']) #rbid[0]) #store the node in the right bucket
		log("Holding wave 1 value message.")
		hold_message(message, 'wave1_wait')	#store the message so the adversary can process them as a batch

		if len(thisInstance['wave_one_bracha_values'][0])+len(thisInstance['wave_one_bracha_values'][1]) == num_nodes:
			#once everyone has reported in, start changing values.
			#yeah, yeah, I know. The adversary for a fault-tolerant system isn't fault-tolerant itself! It's ironic, isn't it?
	
			#so: we're altering the values of wave 1 messages.
			#how many nodes are already on our side?
			log("About to process held wave 1 value messages.")
			values_target = len(thisInstance['wave_one_bracha_values'][1 if thisInstance['target_value'] else 0])
			#how many nodes are against us?
			values_nontarget = len(thisInstance['wave_one_bracha_values'][0 if thisInstance['target_value'] else 1])
		
			messages_to_change = 0
			dir_to_change_to = None
		
			if thisInstance['gameplan'] == 'split_vote' or thisInstance['gameplan'] == 'split_hold':
				messages_to_change_to_target = max( (fault_bound+1) - values_target, 0 )
				messages_to_change_to_nontarget = max( (fault_bound+1) - values_nontarget, 0 )
				#make sure there's at least t+1 of each for split_vote or split_hold

			elif thisInstance['gameplan'] == 'force_decide':
				messages_to_change_to_target = max( (fault_bound+1) - values_target, 0 )
				messages_to_change_to_nontarget = 0
				#we only need t+1 target for force_decide

			elif thisInstance['gameplan'] == 'lie_like_a_rug':
				messages_to_change_to_target = min(fault_bound, values_nontarget) 
				messages_to_change_to_nontarget = 0
				#naive adversary - change as many nodes to target as we can!
			
				#this may be the simplest, because it has no timing changes.
				#If we have no target, we pick the first N nodes that darken our doorways 
			else: 
				#if we somehow got here, failsafe: do nothing
				#TODO: print warning
				messages_to_change_to_target = 0
				messages_to_change_to_nontarget = 0
		
			if messages_to_change_to_nontarget == 0:
				messages_to_change = messages_to_change_to_target
				dir_to_change_to = thisInstance['target_value']
			elif messages_to_change_to_target == 0:
				messages_to_change = messages_to_change_to_nontarget
				dir_to_change_to = not thisInstance['target_value']
			else: #both are nonzero
				print "Error: Ended up having to change messages in both directions!"
				exit()
		
			log("Messages stack up at {}T/{}F; changing {} messages to {}.".format(thisInstance['wave_one_bracha_values'][1],thisInstance['wave_one_bracha_values'][0],messages_to_change,dir_to_change_to))
		
			messages_actually_changed = 0
			#now actually change all those held messages
			for thisMessage in thisInstance['held_messages']['wave1_wait']:
				if messages_to_change == 0 or message['body'][2][0] == dir_to_change_to:
					return_value_message(thisMessage) #don't change anything
				else:
					messages_to_change -= 1
					altered_message, changed = maybe_change_bracha_message(thisMessage, dir_to_change_to)
					if changed:
						messages_actually_changed += 1
					return_value_message(altered_message)
		
			log("Was able to alter {} messages.".format(messages_actually_changed))
			thisInstance['held_messages']['wave1_wait'] = [] #now clear messages
			#iter_rollover(thisInstance,'bracha','value') #next iteration and/or epoch
			thisInstance ['wave_one_bracha_values'] = [set(),set()] #clear out bracha message buckets
	elif wave == 2:
		if thisInstance['gameplan'] == 'force_decide':
			#for force_decide, the overtaken nodes will still emit the original value on wave 2 - this is because they store their natural emitted wave 1 value and reject the altered copy. So, the adversary has to alter their values on wave 2, too.
			if value != thisInstance['target_value']:
				altered_message, changed = maybe_change_bracha_message(message, thisInstance['target_value'])
				if changed:
					log("Changed message value to {}".format(altered_message['body'][2][0]))
			log("Returning message.")
			return_value_message(altered_message)
				
	elif wave == 3:
		deciding = message['body'][2][1] #get deciding flag
	else: 
		#wtf?
		#TODO: throw exception
		pass
	
	
	
	if wave != 1: #the adversary doesn't interfere with the value of Wave 2+ bracha messages.
	#exception is for Lie Like A Rug, in which case it changes the values on its own nodes to match target, or just flip.
		if thisInstance['gameplan'] == 'lie_like_a_rug':
			#adversary prepares fake message
			altered_message, changed = maybe_change_bracha_message(message, (False if value else True) if thisInstance['target_value'] is None else thisInstance['target_value'] ) #overwrite message, if possible. if we don't have a target, swap the bit of the message. If we do have a target, set the value to that.
			if changed:
				log("Changed message value to {}".format(altered_message['body'][2][0]))
			log("Returning message.")
			return_value_message(altered_message)
			return
		else:
			log("Returning message.")
			return_value_message(message)
			
			if wave == 2:
				thisInstance['wave_two_messages_counted'] += 1
				
				if message['sender'] in thisInstance['held_messages']['timing_holds'][1]: #held msgs present?
					messages_to_release = thisInstance['held_messages']['timing_holds'][1][message['sender']]
					log("Releasing {} wave 1 timing hold messages for {}.".format(len(messages_to_release),message['sender']))
					thisInstance['held_messages']['timing_holds'][1][message['sender']] = [] #remove held messages
					for released_message in messages_to_release:
						return_timing_message(released_message)
					
				
			#we ignore wave 2/3 messages
			if wave == 3:
				thisInstance['wave_three_messages_counted'] += 1
				
				if message['sender'] in thisInstance['held_messages']['timing_holds'][2]: #held msgs present?
					messages_to_release = thisInstance['held_messages']['timing_holds'][2][message['sender']]
					log("Releasing {} wave 2 timing hold messages for {}.".format(len(messages_to_release),message['sender']))
					thisInstance['held_messages']['timing_holds'][2][message['sender']] = [] #remove held messages
					for released_message in messages_to_release:
						return_timing_message(released_message)
			# 
# 			if thisInstance['wave_two_messages_counted'] == num_nodes:
# 					iter_rollover(thisInstance,'bracha','value') #next iteration and/or epoch, so 
# 					
# 					
# 				#TODO: release held wave 3 timing messages for this node.
			
			
			return
			
			#BELOW: old 
			# if node_is_overtaken(instance, sender): #nodes are decided to be overtaken in Wave 1.
# 					value = list(message['body'][2]) 
# 					if instances[instance]['target_value'] is None: #adversary overwrites value
# 						value[0] = False if value[0] else True #swap value if adv has no target
# 					else:
# 						value[0] = instances[instance]['target_value'] #set to target value
# 					#don't alter deciding in any case. this instruction might change later.
# 					message['body'][2] = tuple(value)
# 					return_message(message) #return lying message
# 				else: 
# 					return_message(message)	#return untouched message if this node isn't one the adversary can take over
			
	
	#past this point assert wave == 1		
	
	
	
	
def process_bracha_message_timing(message,thisInstance):#rbid,thisInstance):
	#this is handled similarly to bracha message value. We wait for all messages to come in, then release them in a set order. 
	#the most common behavior for the adversary will be to release certain messages, then hold the rest until the end of the iteration.
	
	log("{} Received bracha timing message {}, from {} to {}.".format(thisInstance['ID'],message['body'],message['meta']['rbid'][0],message['sender']))
	
	if thisInstance['gameplan'] == 'lie_like_a_rug' or thisInstance['gameplan'] == None:
		log("Returning message - this gameplan doesn't alter timing.")
		return_timing_message(message) #shaker doesn't alter message values, ever. It just messes with timing.
		return
	#TODO: add EOI check.

	#TODO: add 'shaker'
	
	wave = int(message['body'][1])
	value = message['body'][2][0]
	sender = message['sender'] 
	
	if wave == 3:
		deciding = message['body'][2][1]
		
	if thisInstance['timing_quotas'][wave] is None:
		#no quota - return
		log("Returning message - no quota.")
		return_timing_message(message)
	else:
		quota = thisInstance['timing_quotas'][wave][sender]
		if wave == 1 or wave == 2:
			quota = thisInstance['timing_quotas'][wave][sender][1 if value else 0]
			if quota > 0:
				log("Returning message - in quota. (left: {}T/{}F)".format(thisInstance['timing_quotas'][wave][sender][1],thisInstance['timing_quotas'][wave][sender][0]))
				thisInstance['timing_quotas'][wave][sender][1 if value else 0] -= 1
				return_timing_message(message) #OK, clear to go. Send it out.
			else:
				log("Holding message.")
				hold_message_timing(message, sender, wave)
		elif wave == 3:
			quota = thisInstance['timing_quotas'][wave][sender][1 if deciding else 0]
			if quota > 0:
				log("Returning message - in quota. (left: {}T/{}F)".format(thisInstance['timing_quotas'][wave][sender][1],thisInstance['timing_quotas'][wave][sender][0]))
				thisInstance['timing_quotas'][wave][sender][1 if deciding else 0] -= 1
				return_timing_message(message) #OK, clear to go. Send it out.
			else:
				log("Holding message.")
				hold_message_timing(message, sender, wave)


	return	
	
def process_coin_message_value(message,thisInstance):#rbid,thisInstance):
	##KNOWN GAMEPLANS: wedge, blast, wedge_blast, lie_like_a_rug
	##'wedge' - use timing to favor nodes that have their coins go a set way (TIMING)
	##'blast' - take over some nodes and have them lie about their flips (VALUE)
	##'wedge_blast' - both wedge and blast at once (VALUE+TIMING)
	##'lie_like_a_rug' - take over some nodes and have them lie about ALL their flips (unconvincing) (VALUE)

	if thisInstance['gameplan_coin'] == 'wedge' or thisInstance['gameplan_coin'] == None:
		return_value_message(message) #wedge by itself doesn't alter messages.
		
	#but we're not messing with coin messages for now. TODO
	return_value_message(message)
	return
	
	#return message, for now #TODO
		
def process_coin_message_timing(message,thisInstance): #rbid,thisInstance):
	if thisInstance['gameplan_coin'] == 'blast' or thisInstance['gameplan_coin'] == 'lie_like_a_rug' or thisInstance['gameplan_coin'] == None:
		return_timing_message(message) #blast and lie-like-a-rug don't alter message timing.

	return_timing_message(message) #TODO: for now, do nothing
	return


def process_message_client(message):
	global current_master_gameplan_bracha, current_master_gameplan_coin
	#assume it's a gameplan change method
	try:
		mode = message['meta']['mode']
	except IndexError:
		MessageHandler.send("Received invalid adversary command.", None,'client', type_override='announce')
	
	
	if mode == 'set_gameplan':
		try:
			bracha_changed = False
			coin_changed = False
			if message['body'][0].lower() in known_bracha_gameplans and message['body'][0].lower() != current_master_gameplan_bracha:
				current_master_gameplan_bracha = message['body'][0].lower()
				bracha_changed = True
				if current_master_gameplan_bracha == 'none':
					current_master_gameplan_bracha = None
				log("Changed Bracha gameplan to {}.".format(current_master_gameplan_bracha))
			
			if message['body'][1].lower() in known_coin_gameplans and message['body'][1].lower() != current_master_gameplan_coin:	
				current_master_gameplan_coin = message['body'][1].lower()
				coin_changed = True
				if current_master_gameplan_coin == 'none':
					current_master_gameplan_coin = None
				log("Changed Coin gameplan to {}.".format(current_master_gameplan_coin))
		
			if bracha_changed or coin_changed:
				MessageHandler.send("Changed adversarial{} gameplan to {}{}{}.".format('' if (bracha_changed and coin_changed) else (' bracha' if bracha_changed else ' coin'), current_master_gameplan_bracha if bracha_changed else '', '/' if bracha_changed and coin_changed else '', current_master_gameplan_coin if coin_changed else ''), None,'client', type_override='announce')
			else: 
				MessageHandler.send("Couldn't change adversarial gameplan.", None,'client', type_override='announce')
		except IndexError:
			MessageHandler.send("Couldn't change adversarial gameplan.", None,'client', type_override='announce')
	elif mode == 'get_gameplan':
		MessageHandler.send("Gameplan is {}/{}.".format(current_master_gameplan_bracha,current_master_gameplan_coin), None,'client', type_override='announce')
	elif mode == 'release':
		try:
			byzID = message['body'][0]
			wave = message['body'][1]
		except IndexError:
			MessageHandler.send("Received invalid adversary command.", None,'client', type_override='announce')
			return	
			
		if byzID not in instances:
			print "Release messages command: unknown byzID '{}'.".format(byzID)
			MessageHandler.send("Received invalid release messages command: unknown byzID '{}'.".format(byzID), None,'client', type_override='announce')	
			return
			
		if wave != 1 and wave != 2 and wave != 3:
			print "Release messages command: invalid wave#."
			MessageHandler.send("Received invalid release messages command: wave {} doesn't exist.".format(wave), None,'client', type_override='announce')
			return
		
		print "Releasing messages for instance {}, wave {} by request.".format(byzID, wave)
		numreturned = 0
		
		for message_bucket in instances[byzID]['timing_holds'][wave]:
			for message in instances[byzID]['timing_holds'][wave][message_bucket]:
				numreturned += 1
				return_timing_message(message, skip_log=True)
		#now clear 'held' list
		instances[byzID]['timing_holds'][wave] = {} 	
		
		print "Returned {} messages.".format(numreturned)
		MessageHandler.send("Returned {} messages for ID {}, wave {}.".format(numreturned,byzID,wave), None,'client', type_override='announce')
		
		
def process_message_special(message):
	#used for handling decide messages, eventually.
	#TODO
	pass		
		

def process_message(message, reprocess=False):
	message_type = message['type']
	if message_type == 'client':
		#do something special
		process_message_client(message)
		return
	
	
	
	instance = get_message_ID(message)
	try:
		rbid = message['meta']['rbid']
		epoch = rbid[2][1]
		iteration = rbid[2][2]
		#sender = rbid[0]
		msgType = bracha_or_coin(message) #'bracha' or 'coin' (or None)
		code = message['code'] if message_type == 'node' else message_type #'value' or 'timing' or special
	except Exception as err:
		print err
		raise err
		
	if msgType is None:
		return #bad message
	if code != 'value' and code != 'timing':
		process_message_special(message)
		return #unusual message
	
	
	maybe_setup_instance(instance)
		
	thisInstance = instances[instance]
		
	# next, check to see that the message isn't old. If it is old, we've stopped interfering with that iteration and we just let it go through.
	# might want to rewrite this later.
	
	if epoch < thisInstance['epoch'][msgType][code]:
		if code == 'value':
			return_value_message(message)
		elif code == 'timing':
			return_timing_message(message)
	elif iteration < thisInstance['iteration'][msgType][code]:
		if code == 'value':
			return_value_message(message)
		elif code == 'timing':
			return_timing_message(message)
	elif epoch > thisInstance['epoch'][msgType][code]:
		hold_message(message, 'future_epoch') # lambda: thisInstance['epoch'] == epoch)
	elif iteration > thisInstance['iteration'][msgType][code]:
		hold_message(message, 'future_iter') # lambda: thisInstance['iteration'] == iteration)
		#TODO: message release for all four of each of iter/epoch holds (so eight buckets to trigger in total)
	else:
		if msgType == 'bracha':
			if code == 'value':
				process_bracha_message_value(message,thisInstance)#rbid,thisInstance)
			elif code == 'timing':
				process_bracha_message_timing(message,thisInstance)#rbid,thisInstance)
		elif msgType == 'coin':
			if code == 'value':
				process_coin_message_value(message,thisInstance)#rbid,thisInstance)
			elif code == 'timing':
				process_coin_message_timing(message,thisInstance)#rbid,thisInstance)

		
	
	

def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	print "Starting up..."
	global num_nodes, fault_bound, majority, minority_bound, all_nodes, instances
		
	if len(args) < 1:
		print "Please provide me with a node list."
		exit()
	
	with open(args[0]) as node_list:
		all_nodes = [line.rstrip() for line in node_list]
	
	MessageHandler.init_adversary()
	
	num_nodes = len(all_nodes)
	fault_bound = (num_nodes - 1) // 3  #t < n/3. Not <=.
	majority = num_nodes - fault_bound #what's n - t?
	minority_bound = majority - (majority // 2 + 1) #what's the largest part you can have of n - t without getting a majority of it?
	
	print "Maximum adversarial nodes: {}/{}.".format(fault_bound, num_nodes)
	
	weSaidNoMessages = False 
	while True:
		#print "Checking for messages."
		
		adv_message = MessageHandler.receive_backchannel(im_adversary=True)
		if adv_message is None:
			if not weSaidNoMessages: #only say 'nobody home' once until we receive messages again.
				print "No messages."
				weSaidNoMessages = True
			sleep(1) #wait a second before we check again.
		else:
			weSaidNoMessages = False
			process_message(adv_message)

	
		
if __name__ == "__main__":
	main(argv[1:])	
else:
	print "Running as {}, dunno what to do.".format(__name__)
	exit()
