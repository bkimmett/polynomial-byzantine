#!/usr/bin/env python

#It's a lot like a firewall with deep packet inspection, really. Except mean.

from __future__ import division #utility
import random					#for coin flips
from sys import argv, exit, stdout, stderr 		#utility
from time import sleep, strftime 	#to wait for messages, and for logging
from math import floor, sqrt		#utility
from math import log as nlog 		#guess who made 'log' be a logging function?
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

known_bracha_gameplans = ['none','split_vote','split_hold','force_decide','lie_like_a_rug'] #there was plans to have a gameplan 'shaker' to play with timing but we're not going to implement that
known_coin_gameplans = ['none','bias','bias_reverse','split']

debug = True
debug_coin_acks = False
debug_messages = False

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
		setup_instance(byzID, target_value=target)	
	return instances[byzID]



def setup_instance(byzID, target_value=None):
	global instances
	instances[byzID] = {}
	#the following items are FIXED BY INSTANCE and not dependent on epoch or iterations.
	instances[byzID]['ID'] = byzID
	instances[byzID]['iters_per_epoch'] = num_nodes * 2 #default iteration constant.
	instances[byzID]['fault_list'] = [] #list of nodes the adversary has overtaken in this instance
	instances[byzID]['gameplan'] = current_master_gameplan_bracha 			#adversarial gameplan (bracha)
	instances[byzID]['gameplan_coin'] = current_master_gameplan_coin 	#adversarial gameplan (global-coin)
	instances[byzID]['target_value'] = target_value

	instances[byzID]['ei_storage'] = {}  #used to store all the stuff that's epoch-iter specific.
	
	
	corrupt_target_bracha = 0
	corrupt_target_coin = 0
	
	if instances[byzID]['gameplan_coin'] == 'split':
		corrupt_target_coin = 3
	elif instances[byzID]['gameplan_coin'] == 'bias' or instances[byzID]['gameplan_coin'] == 'bias_reverse':
		corrupt_target_coin = fault_bound
	
	
	##REMOVE BELOW THIS LINE AFTER setup_iteration() IS WORKING
	# instances[byzID]['held_messages'] = {'wave1_wait':[], 'timing_holds':[None,{},{},{}], 'future_iter':[], 'future_epoch':[]} #storage
# 	instances[byzID]['wave_one_bracha_values'] = [set(),set()] #state: used to keep track of the wave 1 bracha values.
# 	#instances[byzID]['wave_two_messages_counted'] = 0
# 	#instances[byzID]['wave_three_messages_counted'] = 0
# 	instances[byzID]['decide_messages_counted'] = 0
# 	instances[byzID]['timing_quotas'] = None #setup_quotas(instances[byzID]['gameplan'], all_nodes, target_value)
	
	#the following items are DEPRECATED and will become unused.
	#instances[byzID]['epoch'] = {'bracha':{'value':0, 'timing':0}, 'coin':{'value':0, 'timing':0}}
	#instances[byzID]['iteration'] = {'bracha':{'value':0, 'timing':0}, 'coin':{'value':0, 'timing':0}} #the adversary, because it has stalling decisions over the rest of the game, tracks these separately.
	
	
def setup_iteration(thisIteration, byzID, target_value=None):		
	#the following items are FLEXIBLE and are dependent on epoch/iteration.
	thisIteration['ID'] = byzID
	thisIteration['instance'] = instances[byzID]
	thisIteration['held_messages'] = {'wave1_wait':[], 'timing_holds':[None,{},{},{}], 'coin_initial':[], 'coin_final':[]} # , 'future_iter':{}, 'future_epoch':{}} #storage
	thisIteration['wave_one_bracha_values'] = [set(),set()] #state: used to keep track of the wave 1 bracha values.
	#thisIteration['wave_two_messages_counted'] = 0
	#thisIteration['wave_three_messages_counted'] = 0
	thisIteration['decide_messages_counted'] = 0
	thisIteration['timing_quotas'] = None #setup_quotas(thisIteration['gameplan'], all_nodes, target_value)
	
	thisIteration['coin_balance'] = 0
	thisIteration['initial_coin_hold_balance'] = 0
	thisIteration['ignore_coin_messages_from'] = []
	thisIteration['coin_columns_complete'] = 0
	thisIteration['good_columns_complete'] = 0
	thisIteration['nodes_done'] = 0
	thisIteration['adversary_column_plans_sent'] = False
	#the following items are DEPRECATED and will become unused.
	#instances[byzID]['epoch'] = {'bracha':{'value':0, 'timing':0}, 'coin':{'value':0, 'timing':0}}
	#instances[byzID]['iteration'] = {'bracha':{'value':0, 'timing':0}, 'coin':{'value':0, 'timing':0}} #the adversary, because it has stalling decisions over the rest of the game, tracks these separately.
	#TODO: Iteration turnover.
	
def get_EI(message): #extract E/I from message and get EI with it
	msgmeta = message['meta']['rbid'][2]
	#print "Trying to get EI for meta {}.".format(msgmeta)
	return setup_or_get_EI(*msgmeta)
	
def setup_or_get_EI(byzID, epoch, iteration):
	#print "Called with {}, {}, {}.".format(byzID,epoch,iteration)
	thisInstance = maybe_setup_instance(byzID)
	
	if epoch not in thisInstance['ei_storage']:
		thisInstance['ei_storage'][epoch] = {}
		thisInstance['ei_storage'][epoch][iteration] = {}
		#thisInstance['ei_storage'][epoch][iteration] = 
		setup_iteration(thisInstance['ei_storage'][epoch][iteration], byzID, target_value=thisInstance['target_value'])
	elif iteration not in thisInstance['ei_storage'][epoch]:
		#thisInstance['ei_storage'][epoch][iteration] = 
		thisInstance['ei_storage'][epoch][iteration] = {}
		setup_iteration(thisInstance['ei_storage'][epoch][iteration], byzID, target_value=thisInstance['target_value'])

	return thisInstance['ei_storage'][epoch][iteration]

def num_nodes_overtaken(iteration):
	return len(get_nodes_overtaken(iteration))
	
def get_nodes_overtaken(iteration):
	return iteration['instance']['fault_list']
	
def setup_quotas(gameplan, node_message_list, target_value, corrupted_nodes, corruption_dir,  wave1_values): #target_count, nontarget_count):
	quota_list = [None,None,None,None]
	target_count = wave1_values[1 if target_value else 0]
	nontarget_count = wave1_values[0 if target_value else 1]
	
	
	if gameplan is None:
		return quota_list
	elif target_value is None:
		print "Error: Tried to set up quotas for a gameplan without a target value. Not using quotas."
		return quota_list
		
	#reminder:	[1 if target_value else 0] means you're storing the TARGET QUOTA.
	#			[0 if target_value else 1] means you're storing the NONTARGET QUOTA.		

	#quotas can be None (no quota), or a dict (quota for each node). Inside that dict, you have either a None (no quota for that node) or a list (quota of true, false messages).
	
	node_list = [[message['sender'],message['body'][2][0]] for message in node_message_list]
	
	if gameplan == "force_decide":
		quota_list[1] = {}
		for node in node_list: 
			quota_list[1][node[0]] = [minority_bound,num_nodes] if target_value else [num_nodes,minority_bound]
			quota_list[1][node[0]][1 if (corruption_dir if node[0] in corrupted_nodes else node[1]) else 0]	-= 1 #decrement the node's quota by 1 for its original self message.
			#the above line originally said "1 if node[1] else 0" and its purpose was to decrement the quota by its original message value, so that when the lie came back to that node and was rejected, everything would line up. We still need to subtract one from the quota, because self messages travel free - but the node is forced to lie, so we decrement the quota by one for the lying message instead.
		print repr(quota_list[1])
		return quota_list
		
	if gameplan == "split_vote":
		quota_list[1] = {}
		quota_list[2] = {}
		flip = target_value
		force_minority_counter = len(corrupted_nodes)
		
		if target_count >= nontarget_count:
			majority_val = target_value
		else:
			majority_val = not target_value
		
		for node in node_list: 
			#quota_list[2][node[0]] = [num_nodes // 2, num_nodes // 2] #we won't get more than n/2 wave 2 messages of either type, so the deciding flag is never set
			
			if node[0] in corrupted_nodes:
				quota_list[1][node[0]] = [minority_bound,num_nodes] if majority_val else [num_nodes,minority_bound] #set quota so node receives majority value		
				if majority_val:
					quota_list[2][node[0]] = [num_nodes // 2, num_nodes // 2 - 1] #node will emit 'true' in wave 1, so account for that in its wave 2 quota
				else:
					quota_list[2][node[0]] = [num_nodes // 2 - 1, num_nodes // 2] #will emit 'false', alter quota
						
			elif force_minority_counter > 0:
				quota_list[1][node[0]] = [minority_bound,num_nodes] if not majority_val else [num_nodes,minority_bound] #set quota so that node receives minority value - to counterbalance majority value going to corrupted nodes
				force_minority_counter -= 1
				
				if not majority_val:
					quota_list[2][node[0]] = [num_nodes // 2, num_nodes // 2 - 1] #will emit 'true', alter quota
				else:
					quota_list[2][node[0]] = [num_nodes // 2 - 1, num_nodes // 2] #will emit 'false', alter quota
				
			else:
				#distribute nodes evenly
				quota_list[1][node[0]] = [minority_bound,num_nodes] if flip else [num_nodes,minority_bound] #true flip yields 'True' wave 2 message - false flip yields 'False' wave 2 message - this ensures the wave 2 messages are split half and have and the wave 2 quota works
				
				if flip:
					quota_list[2][node[0]] = [num_nodes // 2, num_nodes // 2 - 1] #will emit 'true', alter quota
				else:
					quota_list[2][node[0]] = [num_nodes // 2 - 1, num_nodes // 2] #will emit 'false', alter quota
				
				flip  = not flip
				
			quota_list[1][node[0]][1 if (corruption_dir if node[0] in corrupted_nodes else node[1]) else 0]	-= 1 #decrement the node's quota by 1 for its self message.
		print repr(quota_list[1])
		return quota_list	
		
	if gameplan == "split_hold":
		
		quota_list[1] = {}
		quota_list[2] = {}
		quota_list[3] = {}
		#the adversary needs two node populations of sizes 2t to pull this off. Let's randomize them - it'll make it easier to check that end-of-wave held message release is working properly. Also, it's something a real adversary might do to make it harder to be detected.
		wave_one_subsample = random.sample(node_list,max(2*fault_bound, num_nodes // 2 + 1)) #this population might be larger than 2t if t is small
		wave_two_subsample = random.sample(node_list,2*fault_bound) #this population is always 2t big. We don't want more nodes popping the decide flag.
		
		for node in node_list:
			quota_dir = None
			
			
			if node in wave_one_subsample:
				quota_list[1][node[0]] = [minority_bound,num_nodes] if target_value else [num_nodes,minority_bound] #ensure target value is emitted
				quota_dir = target_value
			else:
				quota_list[1][node[0]] = [num_nodes,minority_bound] if target_value else [minority_bound,num_nodes] #nontarget value is emitted
				quota_dir = not target_value
				
			quota_list[1][node[0]][1 if (corruption_dir if node[0] in corrupted_nodes else node[1]) else 0]	-= 1
			#post wave 1: (assuming target is TRUE):
			#2t TRUE2, rest FALSE2
			#for smaller t's:
			#n/2+1 TRUE2, rest FALSE2
			
			if node in wave_two_subsample: #selected to emit Target,True
				quota_list[2][node[0]] = [majority - (num_nodes // 2 + 1),num_nodes] if target_value else [num_nodes,majority - (num_nodes // 2 + 1)] #ensure target value is emitted (wave 2 ver) WITH deciding flag and our target value
				
				quota_list[3][node[0]] = [majority - (fault_bound + 1),fault_bound*2 - 1] 
				#wave 3 quotas are strange; instead of determining by value, [False,True]
				#they determine by the deciding flag being set to [False,True].
				#so here, we allow up to 2t deciding messages. 
				#We always want t+1 deciding messages or more. So we only allow (n-t) - (t+1) non-deciding messages, because that guarantees at least t+1 decidings get through.
				
				#we also subtract 1 from the 'True' side of the wave 3 quota to allow for the counting of the self message.
			else: #selected to emit any,False
				quota_list[2][node[0]] = [num_nodes // 2, num_nodes // 2] 
				quota_list[3][node[0]] = [majority - (fault_bound + 1) - 1,fault_bound*2] 
				#ensure deciding flag IS NOT emitted. We don't care about the values that much.
				#this can't hang because the number of messages required to progress to the next stage will ALWAYS be less than the number the quota will allow, for t < n/3
				
				#see in mathematica:
#				 Block[{n = 10000},
# 				 Plot[{
# 				   n - t,
# 					Min[Floor[n/2], Max[2 t, Floor[n/2] + 1]] + 
# 					 Min[Floor[n/2], n - Max[2 t, Floor[n/2] + 1]]
# 				   }, {t, 1/3*n, 1}]]
			if quota_dir:
				quota_list[2][node[0]][1] -= 1 #subtract 1 from wave 2 quota to compensate for 'True' self message
			else:
				quota_list[2][node[0]][0] -= 1 #...for 'False' self message
				
			#post wave 2:
			#2t #, DECIDING
			#rest NOT DECIDING	
			
			#quota_list[3][node[0]] = [majority - (fault_bound + 1),fault_bound*2] 
			
		print repr(quota_list[1])
		print repr(quota_list[2])
		print repr(quota_list[3])
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
	#instance = get_message_ID(message)
	#maybe_setup_instance(instance)
	iteration = get_EI(message)

	#instances[instance]['held_messages'][key].append(message)
	iteration['held_messages'][key].append(message)	
	
def hold_message_timing(message,sender,wave):
	#instance = get_message_ID(message)
	#maybe_setup_instance(instance)
	iteration = get_EI(message)

	log("[{}] Holding wave {} timing message [{}] from {} to {}.".format(iteration['ID'],wave,message['body'],message['meta']['rbid'][0],sender))

	if sender not in iteration['held_messages']['timing_holds'][wave]:
		iteration['held_messages']['timing_holds'][wave][sender] = []
		
	iteration['held_messages']['timing_holds'][wave][sender].append(message)

	#if sender not in instances[instance]['held_messages']['timing_holds'][wave]:
	#	instances[instance]['held_messages']['timing_holds'][wave][sender] = []
		
	#instances[instance]['held_messages']['timing_holds'][wave][sender].append(message)
	
	
def release_messages(thisIteration, key): #, message_processor):

	temp_messages_bucket = thisIteration['held_messages'][key] #copy messages into temp bucket
	thisIteration['held_messages'][key] = [] #clear actual message bucket

	for message in temp_messages_bucket:
		#process each held message again
		#message_processor(message)
		process_message(message, reprocess=True)
		
	
	#clear messages
	
#TODO: rewrite these functions so they take an instance or iteration object, it's getting hard to remember what needs what
	
def node_is_overtaken(instancename, nodename):
	return nodename in instances[instancename]['fault_list']	
	
def send_node_gameplans(instance, nodename, plan, type="gameplan_bracha"):
	if maybe_overtake_node(instance, nodename):
		log("[{}] Sending gameplan {} to node {}.".format(instance,plan,nodename))
		MessageHandler.send([type, instance, plan], None, nodename, type_override='adversary_command')
		return True
	
	return False #we couldn't overtake this node, so no send
		
	
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
	elif message['body'][0] == MessageMode.adv_notify:
		return 'notify'
		
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
			
			
def maybe_change_bracha_message(message, new_value, skip_nonadversarial=False):
	#wrapper to change bracha values
	updated_value = list(message['body'][2])
	updated_value[0] = new_value
	updated_body = message['body'][:] #copy
	updated_body[2] = tuple(updated_value)
				
	#altered_message, success = maybe_change_message(message, updated_body) #overwrite message, if possible				
	return maybe_change_message(message, updated_body, only_if_node_already_overtaken=skip_nonadversarial) #overwrite message, if possible

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
	
	thisIteration = get_EI(message)
	
	#figure out what wave it is
	wave = int(message['body'][1])
	value = message['body'][2][0]
	
	if wave != 1 and wave != 2 and wave != 3:
		#WTF? bad wave value
		log("Received a message with a bad wave value: {}. Discarding.".format(wave))
		return 
	
	#When receiving a message, whether we change it or not, alter the node's personal quota to reduce it by one for its original value. This prevents jams where the node can decide inconsistently - the node pre-receives its own message, so we alter the quota to accommodate it. Self-sent messages then travel for free, ignoring quota. (We could always not let them through, with an indefinite hold - in case we're worried about nodes catching on that their value has been altered. But it's easier to just let the messages through for now.)
	# A former concern: Sooner or later some node will get its quota decremented late 'cause it sent out its value very late, AFTER all the messages have come in and made it decide in a way the adversary didn't want. There's no good way to handle this while maintaining full async. The adversary could also hold off on letting the node receive messages for a wave until it's sent its own value, but this is an advanced enough scenario that if it goes wrong we can just rerun the tests again.
	#
	#...making an adversary is hard. Also, old man Bracha was a genius. 
	
	#PS: The above concern was resolved by having the quota setup take place after wave 1 values are known, and wave 2/3 values can be predicted. 
	
	# if thisInstance['timing_quotas'] is not None:
# 		if thisInstance['timing_quotas'][wave] is not None:
# 			if thisInstance['timing_quotas'][wave][message['sender']] is not None:
# 				if thisInstance['timing_quotas'][wave][message['sender']][1 if message['body'][2][0] else 0] > 0:
# 					thisInstance['timing_quotas'][wave][message['sender']][1 if message['body'][2][0] else 0] -= 1
	
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
	
	#shaker, None, and lie_like_a_rug (bracha gameplans) do not use timing quotas, so we can skip setting them up.
	
	if wave == 1:
		if len(thisIteration['wave_one_bracha_values'][0])+len(thisIteration['wave_one_bracha_values'][1]) == num_nodes:
			#if we're already at full, the extra messages are from corrupted nodes, and get VIP treatment.
			return_value_message(message)
			return
			
			
		thisIteration['wave_one_bracha_values'][1 if value else 0].add(message['sender']) #rbid[0]) #store the node in the right bucket
		log("Holding wave 1 value message.")
		hold_message(message, 'wave1_wait')	#store the message so the adversary can process them as a batch

		if len(thisIteration['wave_one_bracha_values'][0])+len(thisIteration['wave_one_bracha_values'][1]) == num_nodes:
			#once everyone has reported in, start changing values.
			#yeah, yeah, I know. The adversary for a fault-tolerant system isn't fault-tolerant itself! It's ironic, isn't it?
	
			#so: we're altering the values of wave 1 messages.
			#how many nodes are already on our side?
			log("About to process held wave 1 value messages.")
			values_target = len(thisIteration['wave_one_bracha_values'][1 if thisInstance['target_value'] else 0])
			#how many nodes are against us?
			values_nontarget = len(thisIteration['wave_one_bracha_values'][0 if thisInstance['target_value'] else 1])
		
			if values_target == 0 or values_nontarget == 0:
				#if EVERY node has the same value, the adversary can't do anything. Give up as a convenience measure - otherwise, the experimenter would have to use an 'adv_release' command to continue the iteration if it were under a split_vote or split_hold gameplan (the adversary would make it hang with its indefinite holds).
				log("Every node is unanimous. Taking no action for this iteration (gameplans from past iterations may carry over for Wave 2/3, but won't have any effect on the outcome).")
				for thisMessage in thisIteration['held_messages']['wave1_wait']:
					return_value_message(thisMessage) #return all messages
				
				thisIteration['timing_quotas'] = None #quotas can't change anything either, so don't add any
				return
				
		
			messages_to_change = 0
			dir_to_change_to = None
			gameplan_to_load = [None,None,(None,None)]
		
			if thisInstance['gameplan'] == 'split_vote' or thisInstance['gameplan'] == 'split_hold':
				messages_to_change_to_target = max( (fault_bound+2) - values_target, 0 )
				messages_to_change_to_nontarget = max( (fault_bound+2) - values_nontarget, 0 )
				
				if messages_to_change_to_target > 0 and messages_to_change_to_nontarget == 0:
					gameplan_to_load = [thisInstance['target_value'], None, None]
				elif messages_to_change_to_target == 0 and messages_to_change_to_nontarget > 0:
					gameplan_to_load = [not thisInstance['target_value'], None, None]
				else:
					pass #no changes
				
				#make sure there's at least t+1 of each for split_vote or split_hold
				#try to get t+2 if we can tho - this'll allow for nodes that recognize their own message being altered and reject it to still see t+1 of each type
				#ideally, though, the adversarial nodes should have quotas to expect the majority value, excluding that node's own altered value
				#this means the adversarial node will handle things as normal, with the self-values excluded from node quotas.
				#at this point in the whole business, all value messages have been held, so we CAN still alter quotas without producing undefined behavior.

			elif thisInstance['gameplan'] == 'force_decide':
				messages_to_change_to_target = max( (fault_bound+2) - values_target, 0 )
				messages_to_change_to_nontarget = 0
				gameplan_to_load = [thisInstance['target_value'],thisInstance['target_value'],(thisInstance['target_value'],True)]
				#we only need t+1 target for force_decide
				#but we try to get t+2

			elif thisInstance['gameplan'] == 'lie_like_a_rug':
				messages_to_change_to_target = min(fault_bound, values_nontarget) 
				messages_to_change_to_nontarget = 0
				gameplan_to_load = [thisInstance['target_value'],thisInstance['target_value'],(thisInstance['target_value'],None)]
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
		
			log("Messages stack up at {}T/{}F; changing {} messages to {}.".format(thisIteration['wave_one_bracha_values'][1],thisIteration['wave_one_bracha_values'][0],messages_to_change,dir_to_change_to))
		
			messages_actually_changed = []
			#now actually change all those held messages
			for thisMessage in thisIteration['held_messages']['wave1_wait']:
				#log("Deciding whether to change message from {} with value {}.".format(thisMessage['sender'],thisMessage['body'][2][0]))
				
				
				if messages_to_change == 0 or thisMessage['body'][2][0] == dir_to_change_to:
					#log("Decided: not changing.")					
					return_value_message(thisMessage) #don't change anything
				else:
					#log("Changing message.")
					
					changed = send_node_gameplans(thisInstance['ID'], thisMessage['sender'], gameplan_to_load)
					#changed = maybe_overtake_node(thisInstance['ID'], thisMessage['sender'])
					#altered_message, changed = maybe_change_bracha_message(thisMessage, dir_to_change_to)
					if changed:
						messages_to_change -= 1
						messages_actually_changed.append(thisMessage['sender'])
						continue #drop message - corrupted node will resend
						##TODO - VERY IMPORTANT: Right now, the adversary doesn't handle multiple iterations too well. It doesn't make preferential use of nodes it's already corrupted - it's kinda naive. But it should be sufficient. Manipulating bracha... isn't actually that hard if you have at least one good node that starts different from the others, and you're sure no one is looking over your shoulder.
						
						
					return_value_message(thisMessage) #otherwise OK to go
		
			thisIteration['timing_quotas'] = setup_quotas(thisInstance['gameplan'], thisIteration['held_messages']['wave1_wait'], thisInstance['target_value'], messages_actually_changed, dir_to_change_to, thisIteration['wave_one_bracha_values'])
		
			log("Was able to alter {} messages.".format(len(messages_actually_changed)))
	
	else:
		return_value_message(message) #message not altered	
		
	if thisIteration['timing_quotas'] == None:
		return #there's no need to release messages if we didn't set a quota to hold them in the first place.
		
	# elif wave == 2:
# 		if thisInstance['gameplan'] == 'force_decide':
# 			#for force_decide, the overtaken nodes will still emit the original value on wave 2 - this is because they store their natural emitted wave 1 value and reject the altered copy. So, the adversary has to alter their values on wave 2, too.
# 			if value != thisInstance['target_value']:
# 				altered_message, changed = maybe_change_bracha_message(message, thisInstance['target_value'], skip_nonadversarial=True)
# 				if changed:
# 					log("Changed message value to {}".format(altered_message['body'][2][0]))
# 				log("Returning message.")
# 				return_value_message(altered_message)
# 			else: 
# 				return_value_message(message)
# 		elif thisInstance['gameplan'] == 'lie_like_a_rug':
# 			#adversary prepares fake message
# 			altered_message, changed = maybe_change_bracha_message(message, (False if value else True) if thisInstance['target_value'] is None else thisInstance['target_value'] ) #overwrite message, if possible. if we don't have a target, swap the bit of the message. If we do have a target, set the value to that.
# 			if changed:
# 				log("Changed message value to {}".format(altered_message['body'][2][0]))
# 			log("Returning message.")
# 			return_value_message(altered_message)
# 		else:
# 			#gameplan doesn't affect this
# 			log("Returning message.")
# 			return_value_message(message)
# 				
# 	elif wave == 3:
# 		deciding = message['body'][2][1] #get deciding flag
# 		
# 		if thisInstance['gameplan'] == 'force_decide':
# 			#for force_decide, the overtaken nodes will still emit the original value on wave 3, too, so we pretend they're deciding with the target value.
# 			if value != thisInstance['target_value']:
# 				altered_message, changed = maybe_change_bracha_message(message, thisInstance['target_value'], skip_nonadversarial=True)
# 				if changed:
# 					log("Changed message value to {}".format(altered_message['body'][2][0]))
# 					altered_message['body'][2][1] = True #set deciding flag (adversary's lie, or at least adversary's wishful thinking)
# 				log("Returning message.")
# 				return_value_message(altered_message)
# 			else: 
# 				return_value_message(message)
# 				
# 		elif thisInstance['gameplan'] == 'lie_like_a_rug':
# 			#adversary prepares fake message
# 			altered_message, changed = maybe_change_bracha_message(message, (False if value else True) if thisInstance['target_value'] is None else thisInstance['target_value'] ) #overwrite message, if possible. if we don't have a target, swap the bit of the message. If we do have a target, set the value to that.
# 			if changed:
# 				log("Changed message value to {}".format(altered_message['body'][2][0]))
# 			log("Returning message.")
# 			return_value_message(altered_message)
# 		else:
# 			#gameplan doesn't affect this
# 			log("Returning message.")
# 			return_value_message(message)


	#cleanup - if we have later wave value messages, release earlier wave timing messages now	
	#we used to track iter rollover here, but now we track it on decide messages	
	if wave == 2:
		#thisIteration['wave_two_messages_counted'] += 1
		
		if message['sender'] in thisIteration['held_messages']['timing_holds'][1]: #held msgs present?
			messages_to_release = thisIteration['held_messages']['timing_holds'][1][message['sender']]
			log("Releasing {} wave 1 timing hold messages for {}.".format(len(messages_to_release),message['sender']))
			thisIteration['held_messages']['timing_holds'][1][message['sender']] = [] #remove held messages
			for released_message in messages_to_release:
				return_timing_message(released_message)
		else:
			log("No wave 1 timing hold messages for {} to release.".format(message['sender']))
			#log("Holds: ({})".format(thisIteration['held_messages']['timing_holds'][1]))
			
		thisIteration['timing_quotas'][1][message['sender']] = None #either way, empty quota, so future-arriving messages are also let through	

	if wave == 3:
		#thisIteration['wave_three_messages_counted'] += 1
		
		if message['sender'] in thisIteration['held_messages']['timing_holds'][2]: #held msgs present?
			messages_to_release = thisIteration['held_messages']['timing_holds'][2][message['sender']]
			log("Releasing {} wave 2 timing hold messages for {}.".format(len(messages_to_release),message['sender']))
			thisIteration['held_messages']['timing_holds'][2][message['sender']] = [] #remove held messages
			for released_message in messages_to_release:
				return_timing_message(released_message)
		else:
			log("No wave 2 timing hold messages for {} to release.".format(message['sender']))
			#log("Holds: ({})".format(thisIteration['held_messages']['timing_holds'][2]))		
		
		thisIteration['timing_quotas'][2][message['sender']] = None #empty quota		
	
	return	
		
	
	
	
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
	
	thisIteration = get_EI(message)

	if thisIteration['timing_quotas'] is None or thisIteration['timing_quotas'][wave] is None or thisIteration['timing_quotas'][wave][sender] is None:
		#no quota - return
		log("Returning message - no quota.")
		return_timing_message(message)
	
	elif message['meta']['rbid'][0] == message['sender']:
		log("Returning message - self messages travel free.")
		return_timing_message(message)
		
	else:
		try:
			quota = thisIteration['timing_quotas'][wave][sender]
		except KeyError:
			print "You started the adversary with the wrong node names. Start the adversary again and redo the instance you were trying to do from scratch."
			#MessageHandler.shutdown() #maybe don't do this
			exit()
			
		if wave == 1 or wave == 2:
			quota = thisIteration['timing_quotas'][wave][sender][1 if value else 0]
			
			if quota > 0:
				log("Returning message - in quota. (left: {}T/{}F)".format(thisIteration['timing_quotas'][wave][sender][1],thisIteration['timing_quotas'][wave][sender][0]))
				thisIteration['timing_quotas'][wave][sender][1 if value else 0] -= 1
				return_timing_message(message) #OK, clear to go. Send it out.
			else:
				log("Holding message.")
				hold_message_timing(message, sender, wave)
		elif wave == 3:
			quota = thisIteration['timing_quotas'][wave][sender][1 if deciding else 0]
			if quota > 0:
				log("Returning message - in quota. (left: {}T/{}F)".format(thisIteration['timing_quotas'][wave][sender][1],thisIteration['timing_quotas'][wave][sender][0]))
				thisIteration['timing_quotas'][wave][sender][1 if deciding else 0] -= 1
				return_timing_message(message) #OK, clear to go. Send it out.
			else:
				log("Holding message.")
				hold_message_timing(message, sender, wave)


	return	
	

def track_coinboard_balance(message,thisIteration):
	thisIteration['coin_balance'] += (1 if message['body'][3] else -1)
	return thisIteration['coin_balance']
	
def track_column_completion(message,thisIteration):
	if message['body'][1] >= num_nodes - 1:
		thisIteration['coin_columns_complete'] += 1
		if not node_is_overtaken(thisIteration['ID'],get_message_sender(message)):
			thisIteration['good_columns_complete'] += 1
			log("Good column complete.")
			return True, True
		log("Adversarial column complete.")
		return True, False
	else:
		return False, None
	
def handle_bias_adversary_turn(thisIteration):
	log("Holds are full. Sending coin gameplan to adversarial nodes.")
	
	thisIteration['adversary_column_plans_sent'] = True
	
	target_dir = 1 if thisIteration['instance']['target_value'] else -1
	
	even_or_odd = (num_nodes_overtaken(thisIteration) * num_nodes) % 2 #depending on how many adversarial flips are available, the adversary columns must sum to either an even OR an odd number (with which depending on how many flips there are). This needs to be compensated for when setting up the columns so that the adversary can have full columns and still push as needed.

	if thisIteration['instance']['gameplan_coin'] == 'bias_reverse':
		target_dir *= -1

	if target_dir * thisIteration['coin_balance'] <= 0:
		#This means the two do not have the same sign, so: the adversary must push to make it work.
	
		amount_to_push = 1 - target_dir * thisIteration['coin_balance']	
		amount_to_push += (0 if even_or_odd == abs(amount_to_push) % 2 else target_dir) #compensate for even/odd
	
		log("We have a target of {} and a balance of {}. Applying push of {}.".format(target_dir, thisIteration['coin_balance'], amount_to_push))
	
		if amount_to_push > max_coin_influence_total:
			log("Warning: I don't have enough influence to properly bias this coin flip. Sorry! (needed {}, max infl. {} [{} per column]).".format(amount_to_push, max_coin_influence_total, max_coin_influence_per_column))
			simple_adversary_columns(thisIteration, max_coin_influence_total)
			#print a warning, give up 
		else:
			amount_to_push *= target_dir	
			simple_adversary_columns(thisIteration, amount_to_push)
	else:
		log("We have a target of {} and a balance of {}. Adversarial nodes behave normally.".format(target_dir ,thisIteration['coin_balance']))
		simple_adversary_columns(thisIteration, 0 if even_or_odd == 0 else (-1 * target_dir))

def simple_adversary_columns(thisIteration,amount):

	#this function sets the adversary columns to broadcast coin flips that sum to this amount. 'None' is "do whatever".
	if amount is None:
		log("Coin gameplan for this iteration: None. Adversarial nodes act randomly.".format(amount))
		for node in get_nodes_overtaken(thisIteration):
			adversary_column(node, thisIteration, [random_generator.random() >= 0.5 for _ in xrange(num_nodes)])
		return
		#all adv nodes broadcast pure randomness (supplied by the adversary, but still.)
		
	log("Coin gameplan for this iteration: columns that sum to {}.".format(amount))	 #test run: amount = -7
		
	even_or_odd_per_column = num_nodes % 2 	#test run: 10 % 2 = 0
		
	nodes_to_distribute_to = num_nodes_overtaken(thisIteration) #test run: t = 3
	
	even_amount = abs(amount) // nodes_to_distribute_to #test run: 7 // 3 = 2
	#2 % 2 = 0
	
	if even_amount % 2 != even_or_odd_per_column: 
		even_amount -= 1 #this doesn't trigger
	even_amount *= (1 if amount >= 0 else -1) #even amount now = -2
	# integer division (//) uses floor(), effectively, which has some funny results when dividing a negative number. This works around that.
	
	
	leftover_count = abs((amount - even_amount*nodes_to_distribute_to)/2) #how many nodes get extras?
	
	if (amount - even_amount*nodes_to_distribute_to) % 2 == 1:
		log("Uh-oh. An uneven amount of leftover influence is being supplied to adversarial columns. Fixing this, but it typically indicates a bug in the code.")	
		leftover_count = int(leftover_count+.5) #this is a fix to keep things going, but really should have been handled up the chain	
	
	if leftover_count != 0:
		ordering = random.sample(range(nodes_to_distribute_to),nodes_to_distribute_to)
		
		if abs(even_amount)+2 > max_coin_influence_per_column: 
			log("Warning: I probably don't have enough influence to properly bias this coin flip. I'll do all I can. Sorry! (needed {}, max infl. {} per column).".format(even_amount, max_coin_influence_per_column))
			for node in get_nodes_overtaken(thisIteration):
				adversary_column(node, thisIteration, max_coin_influence_per_column * (1 if even_amount >= 0 else -1))
			return
		
		for node in ordering[0:leftover_count]: #the first x nodes get the leftover
			adversary_column(node, thisIteration, even_amount+(2 if even_amount > 0 else -2))
			
		for node in ordering[leftover_count:]:
			adversary_column(node, thisIteration, even_amount)
			
	else:
		if abs(even_amount) > max_coin_influence_per_column: 
			log("Warning: I don't have enough influence to properly bias this coin flip. Sorry! (needed {}, max infl. {} per column).".format(even_amount, max_coin_influence_per_column))
			for node in get_nodes_overtaken(thisIteration):
				adversary_column(node, thisIteration, max_coin_influence_per_column * (1 if even_amount >= 0 else -1))
			return
	
		for node in get_nodes_overtaken(thisIteration):
			adversary_column(node, thisIteration, even_amount)
	#each adversarial node gets told to do +/- even_amount, +/- 1 if they are picked from leftover_amount
	
	
def adversary_column(node,thisIteration,amount):
	#tells a single adversarial node how much to broadcast for Global-Coin.
	#sending a number means "broadcast flips summing to this number"
	#sending a list means "broadcast this many flips in this order with these values" 
	#(so, if the list is empty no coin flips will be broadcast)
	#sending 'None' means "do nothing"
	send_node_gameplans(thisIteration['ID'], node, amount, type="gameplan_coin")	
	
def process_coin_message_value(message,thisInstance):#rbid,thisInstance):
	if debug_coin_acks or message['body'][0] != MessageMode.coin_ack:
		log("{} Received coin {} value message {} from {}.".format(thisInstance['ID'], "flip" if message['body'][0] == MessageMode.coin_flip else ("list" if message['body'][0] == MessageMode.coin_list else ("ack" if message['body'][0] == MessageMode.coin_ack else "???")),message['body'],message['sender']))
	
	thisIteration = get_EI(message)
	##KNOWN GAMEPLANS: bias, split
	##'bias' - use timing to favor nodes that have their coins go a set way, and have some nodes lie about their flips
	##'bias_reverse' is the same, but use the opposite of the target value.
	##'split' - try to split the value so different good nodes get different values.
	
	
	if thisInstance['gameplan_coin'] == None:
		if message['body'][0] != MessageMode.coin_ack or debug_coin_acks:
			log("Returning message - no gameplan set.")
		return_value_message(message) #Don't alter messages if no gameplan is set.
		return
		
	if message['body'][0] == MessageMode.coin_ack:
		if debug_coin_acks:
			log("Returning message - acknowledgements not altered.")
		return_value_message(message) #Currently there are no gameplans that alter acknowledgements
		return
	
	#thisIteration['initial_coin_hold_balance'] = 0
	#thisIteration['coin_balance'] = 0
	
	message_sender = get_message_sender(message)
	
	is_corrupted_message = node_is_overtaken(thisInstance['ID'], message_sender)

	if thisInstance['gameplan_coin'] == 'bias' or thisInstance['gameplan_coin'] == 'bias_reverse':
		if message['body'][0] == MessageMode.coin_list:
			log("Returning message - lists not altered in this gameplan.")
			#TODO: Make it so that we count coinlists and use that to release held messages later on.
			return_value_message(message) #Coin lists are not altered in this gameplan
			return
	
	
		if thisIteration['ignore_coin_messages_from'] == True or is_corrupted_message or get_message_sender(message) in thisIteration['ignore_coin_messages_from']:
			if is_corrupted_message:
				log("Returning message - from an adversarial node.")
			else:
				log("Returning message - not holding messages from this node.")
			#we're letting this message go through without processing it. 
			track_coinboard_balance(message, thisIteration) #keep track of the coin balance
			
			column_finished, good_column = track_column_completion(message, thisIteration)
			if column_finished and good_column:
				if thisIteration['good_columns_complete'] >= (num_nodes - fault_bound) - num_nodes_overtaken(thisIteration):
					if not thisIteration['adversary_column_plans_sent']:
						handle_bias_adversary_turn(thisIteration)
						#If it's full, the adversary gets to act. This will fill here fairly often
			return_value_message(message) #Message is exempt, or following instructions
			return
	
		
		
		message_value = message['body'][3]
		
		if (message_value != thisInstance['target_value']) ^ (thisInstance['gameplan_coin'] == 'bias_reverse'): # ^ is XOR. Why Python just doesn't have a keyword 'xor' is beyond me. So, if it's a message the adversary 'doesn't like', don't let it go through. Do something about it!
			log("Holding message - not in target direction.")
			
			hold_message(message,'coin_initial')
			#thisIteration['initial_coin_hold_balance'] += 1 if message_value else -1
			#not used for bias
			
			
			if len(thisIteration['held_messages']['coin_initial']) >= num_nodes-fault_bound: #held messages maxed out
				log("Held messages are maxed out! Letting the farthest columns progress.")
				#log(repr(thisIteration['held_messages']['coin_initial']))
				thisIteration['held_messages']['coin_initial'] = sorted(thisIteration['held_messages']['coin_initial'], key = lambda heldMessage: heldMessage['body'][1], reverse = True) #sort in descending order - we want the columns that progressed farthest 
			
				messages_to_release = thisIteration['held_messages']['coin_initial'][0:(num_nodes-2*fault_bound)]
				#split off the messages into the ones to release and the rest
				thisIteration['held_messages']['coin_initial'] = thisIteration['held_messages']['coin_initial'][(num_nodes-2*fault_bound):]
			
				num_messages_to_corrupt = fault_bound - num_nodes_overtaken(thisIteration)
				
				log("Letting {} columns progress, and corrupting {} columns.".format(len(messages_to_release), num_messages_to_corrupt))
				
				#If there are not *t* full corrupted columns at this point, the adversary really wants to control that many ASAP.
				if num_messages_to_corrupt > 0:
					#corrupt the nodes with the least progress
					held_len = len(thisIteration['held_messages']['coin_initial'])
					messages_to_discard = thisIteration['held_messages']['coin_initial'][held_len - num_messages_to_corrupt:]
					thisIteration['held_messages']['coin_initial'] = thisIteration['held_messages']['coin_initial'][:held_len - num_messages_to_corrupt]
					
					for junkMessage in messages_to_discard:
						maybe_overtake_node(thisInstance, get_message_sender(junkMessage))
				
				sender_log_list = []
				
				for message_releasing in messages_to_release:
					sender_log_list.append(get_message_sender(message_releasing))
					if thisIteration['ignore_coin_messages_from'] != True:
						thisIteration['ignore_coin_messages_from'].append(get_message_sender(message_releasing))
					process_coin_message_value(message_releasing,thisInstance)
					#return_value_message(message_releasing)
					#release these messages - we want to use 'process' so that the coinboard balance tracking functions are used.
				
				log("Released messages from columns {}.".format(sender_log_list))
				
				
		
		else:
			log("Returning message - in target direction.")
			track_coinboard_balance(message, thisIteration) #keep track of the coin balance
			column_finished, good_column = track_column_completion(message, thisIteration)
			if column_finished and good_column:
				if thisIteration['good_columns_complete'] >= (num_nodes - fault_bound) - num_nodes_overtaken(thisIteration):
					if not thisIteration['adversary_column_plans_sent']:
						handle_bias_adversary_turn(thisIteration)
						#If it's full, the adversary gets to act. This will fill here occasionally
			return_value_message(message) #good to go
			return
	
		
		#coinflip fmt = marker, message_i, sender, flip value
		
		#hold_message(message,'coin_initial')
	
	elif thisInstance['gameplan_coin'] == 'split':
		pass #TODO: Split gameplan
	
	else:
		log("Returning message - unknown gameplan.")
		#this really should have been caught by the acknowledged gameplan list.
		return_value_message(message) #I don't know WHAT this gameplan I've been given is - give up
		return
	
		
def process_coin_message_timing(message,thisInstance): #rbid,thisInstance):
	if thisInstance['gameplan_coin'] == 'bias' or thisInstance['gameplan_coin'] == 'bias_reverse' or thisInstance['gameplan_coin'] == None:
		return_timing_message(message) #bias doesn't alter message timing, and 'no gameplan' doesn't either
		return
	elif thisInstance['gameplan_coin'] == 'split':
		#we can assume we're in the gameplan 'split' now
		
		if message['body'][0] == MessageMode.coin_ack:
			return_timing_message(message) #split doesn't alter acknowledgement timing
			return
		
		return_timing_message(message) #TODO: for now, do nothing
		return
	else:
		#how did we get here?
		return_timing_message(message) #no idea what we're supposed to be doing - give up
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
			epoch = message['body'][2]
			iter = message['body'][3]
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
		
		for message_bucket in instances[byzID]['held_messages']['timing_holds'][wave]:
			for message in instances[byzID]['held_messages']['timing_holds'][wave][message_bucket]:
				numreturned += 1
				return_timing_message(message, skip_log=True)
		#now clear 'held' list
		instances[byzID]['held_messages']['timing_holds'][wave] = {} 	
		
		print "Returned {} messages.".format(numreturned)
		MessageHandler.send("Returned {} messages for ID {}, wave {}.".format(numreturned,byzID,wave), None,'client', type_override='announce')
		

def process_message_notify(message,thisInstance):	
	#used for handling end-of-bracha/end-of-coin messages. This is typically used to release held messages.	
	thisIteration = get_EI(message)
	#num_nodes_overtaken(thisIteration)
	
	if message['body'][1] == 'bracha_over': #end-of-bracha
		log("Message from {}: done with Bracha.".format(get_message_sender(message)))
		pass
		#if node_is_overtaken(thisIteration['ID'],get_message_sender(message)):
		#	thisIteration['nodes_done'][0] += 1
		
		
		#when to release messages depends on when they were held. If messages are initial-hold, we either need to turn them into final-hold, or wait until every good node is done.
		
		#if messages are final-hold, they already have a specific target. When that target reports in, list that, release final-hold messages, and clear future holds.
		
		
	elif message['body'][1] == 'coin_over': #end of coin_ack
		log("Message from {}: done with Global-Coin.".format(get_message_sender(message)))
		#TODO: coin_final
		
		if node_is_overtaken(thisIteration['ID'],get_message_sender(message)):
			thisIteration['nodes_done'][1] += 1
		
			if thisIteration['nodes_done'][1] >= num_nodes - num_nodes_overtaken(thisIteration) and thisIteration['ignore_coin_messages_from'] != True:
				#release held coin_initial 
				log("Releasing {} held coin_initial messages.".format(len(thisIteration['held_messages']['coin_initial'])))
				
				thisIteration['ignore_coin_messages_from'] = True #ignore all coin messages for initial hold going forward
				for held_message in thisIteration['held_messages']['coin_initial']:
					return_value_message(held_message)
				
	else:
		pass
		#TODO: complain
		
		
def process_message_special(message):
	#used for handling decide messages and start of iteration / epoch messages.
	#TODO
	#for epoch/iter: wait for totality, flip over (release held)
	#for decide: release held if it matters
	
	#thisInstance = get_message_ID(message) #bad. thisInstance should be an instance object. don't do this
	thisIteration = get_EI(message)
	
	#body[0] will also send start of iteration, epoch messages 
	
	if message['body'][0] == 'done':
		thisIteration['decide_messages_counted'] += 1
		#body[1] is the nature of the decision - 'flip' or 'flip_hold' or 'decide'
		
		if message['sender'] in thisIteration['held_messages']['timing_holds'][3]: #held msgs present?
			messages_to_release = thisIteration['held_messages']['timing_holds'][3][message['sender']]
			log("Releasing {} wave 2 timing hold messages for {}.".format(len(messages_to_release),message['sender']))
			thisIteration['held_messages']['timing_holds'][3][message['sender']] = [] #remove held messages
			for released_message in messages_to_release:
				return_timing_message(released_message)
		
		if thisIteration['decide_messages_counted'] == num_nodes:
		##TODO: OK, this doesn't work. All we REALLY need to confirm deciding is that n - t nodes will weigh in and broadcast their 'decide' marker to the adversary. So we turn over and release ALL held messages and stop holding new ones at this moment.
		##BY THE WAY: We should really make this iteration and so on proof.
			#flip iteration
			#thisInstance['held_messages']['wave1_wait'] = [] #now clear messages
			#iter_rollover(thisInstance,'bracha','value') #next iteration and/or epoch
			#thisIteration['wave_one_bracha_values'] = [set(),set()] #clear out bracha message buckets
			
			#thisInstance['iteration']['bracha']['value'] += 1 #update iteration		
			#thisInstance['iteration']['bracha']['timing'] += 1
			thisIteration['timing_quotas'] = None #setup_quotas(instances[byzID]['gameplan'], node_list, target_value) #reset timing quotas
			#release_messages(thisInstance, 'future_iter') #messages held for a future iteration will be reprocessed now.


def process_message(message, reprocess=False):
	message_type = message['type']
	
	if message['type'] == "halt":
		#this is for local-machine testing purposes only.
		print "Received shutdown message. Shutting down."
		MessageHandler.shutdown()
		exit(0)
		
	if debug_messages:
		log("Received raw message: {}".format(message))
	
	if message_type == 'client':
		#do something special
		process_message_client(message)
		return
	
	if message['sender'] not in all_nodes:
		print >> stderr, "You started the adversary with the wrong node names - the adversary just received a message from a node it's never heard of. Start the adversary again. Your current instance may need to be rerun."
		MessageHandler.shutdown()
		exit()
	
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
		
	if code != 'value' and code != 'timing' and code != 'info':
		return #huh?
	
	
	thisInstance = maybe_setup_instance(instance)
		
	 #instances[instance]
		
	# next, check to see that the message isn't old. If it is old, we've stopped interfering with that iteration and we just let it go through.
	# might want to rewrite this later.
	
	# if epoch < thisInstance['epoch'][msgType][code]:
# 		if code == 'value':
# 			return_value_message(message)
# 		elif code == 'timing':
# 			return_timing_message(message)
# 	elif iteration < thisInstance['iteration'][msgType][code]:
# 		if code == 'value':
# 			return_value_message(message)
# 		elif code == 'timing':
# 			return_timing_message(message)
# 	elif epoch > thisInstance['epoch'][msgType][code]:
# 		hold_message(message, 'future_epoch') # lambda: thisInstance['epoch'] == epoch)
# 	elif iteration > thisInstance['iteration'][msgType][code]:
# 		hold_message(message, 'future_iter') # lambda: thisInstance['iteration'] == iteration)
# 		#TODO: message release for all four of each of iter/epoch holds (so eight buckets to trigger in total)
# 	else:
	if msgType == 'bracha':
		if code == 'value':
			process_bracha_message_value(message,thisInstance)#rbid,thisInstance)
		elif code == 'timing':
			process_bracha_message_timing(message,thisInstance)#rbid,thisInstance)
	elif msgType == 'coin':
		##TODO: VERY LARGE TODO: Make it so that coin lists are accounted separately from coin flips / acks
		if code == 'value':
			process_coin_message_value(message,thisInstance)#rbid,thisInstance)
		elif code == 'timing':
			process_coin_message_timing(message,thisInstance)#rbid,thisInstance)
	elif msgType == 'notify':
		process_message_notify(message,thisInstance)
	
	

def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	print "Starting up..."
	global num_nodes, fault_bound, majority, minority_bound, max_coin_influence_per_column, max_coin_influence_total, all_nodes, instances, random_generator
	
	try:
		random_generator = random.SystemRandom()
	except:
		print "Couldn't initialize RNG. Check that your OS/device supports random.SystemRandom()."
		exit()
		
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
	max_coin_influence_per_column = int(floor(5 * sqrt(num_nodes * nlog(num_nodes) ))) #assuming n flips per column
	
	if max_coin_influence_per_column < num_nodes: #if there's leftover column space...
		if (num_nodes - max_coin_influence_per_column) % 2 == 1: #...and an odd number of leftover spaces per column...
			max_coin_influence_per_column -= 1 
			#the other flips in each column have to be SOMETHING, and even if we assume they're balanced, the odd one takes away from the rest.
	
	max_coin_influence_total = max_coin_influence_per_column*fault_bound #assuming n flips per column
	
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
