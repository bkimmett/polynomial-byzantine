#!/usr/bin/env python

#It's a lot like a firewall with deep packet inspection, really. Except mean.

from __future__ import division #utility
import random					#for coin flips
from sys import argv, exit, stdout 		#utility
from time import sleep, strftime 	#to wait for messages, and for logging
from math import floor, sqrt, log 			#utility
from copy import deepcopy 		#utility
import numpy as np 				#for matrix operations in _processEpoch
from json import dumps			#for making UIDs good
import multibyz_kingsaia_network_adversary as MessageHandler 
#getting an error with the above line? 'pip install kombu'
import collections				#for data type checking of messages
#from enum import Enum			#for reliable broadcast and byzantine message mode phasing
#getting an error with the above line? 'pip install enum34'
from blist import blist 		#containers that offer better performance when they get big. maybe unnecessary?
#getting an error with the above line? 'pip install blist'
from multibyz_kingsaia_node_adversary import ByzantineAgreement.MessageMode as MessageMode

# A NOTE ON HOW THE ADVERSARY IS SIMULATED

# All of the communications of the implementation use Reliable Broadcast. Which is remarkably difficult to interfere with... which is kind of the point. So, to simulate it, we have each node add an extra step before it accepts a Reliable Broadcast message.
# The extra step is: the node sends its ID, along with the message it was about to accept, to the simulated adversary. The simulated adversary can choose to return it now (indicating no delay), return it later (indicating delay), or change it (which means the adversary has taken over the original sender of the node and now can broadcast whatever it wants, but is pretending to be normal)


instances = {}

#SETUP:

# set up backchannel

# set up node list, alter quota

# We also need to have separate state tracking for each byzantine instance we know of


def maybe_setup_instance(byzID):	
	if byzID not in instances:
		setup_instance(instance)	
	


def setup_instance(byzID,node_list,target_value=None):
	global instances
	instances[byzID] = {}
	
	instances[byzID]['fault_list'] = [] #list of nodes the adversary has overtaken in this instance
	instances[byzID]['gameplan'] = None #adversarial gameplan
	instances[byzID]['target_value'] = target_value
	instances[byzID]['held_messages'] = {'wave1_wait':[]} #storage
	instances[byzID]['future_messages'] = [] #storage
	instances[byzID]['changed_messages'] = {} #this uses the same UID format that ReliableBroadcast uses in the main thing, so all copies of a message will get changed the same way.
	instances[byzID]['released_messages'] = {} #and if we already released a message, we can't change it further thanks to reliable broadcast.
	instances[byzID]['epoch'] = 0
	instances[byzID]['iteration'] = 0 #the adversary, because it has stalling decisions over the rest of the game, can 
	instances[byzID]['wave_one_bracha_values'] = [[],[]]
	
	
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
		

def return_message(message):
	MessageHandler.sendAsAdversary(message['body'],message['meta'],message['sender'])

def hold_message(message,key):
	instance = get_message_ID(message)
	maybe_setup_instance(instance)

	instances[instance]['held_messages'][key].append(message)	
	
def release_messages(instance, key):
	#only call this when you KNOW messages in a bucket WILL be processed and no new ones will be added by this effect.
	maybe_setup_instance(instance)

	for message in instances[instance]['held_messages'][key]:
		#process each held message again
		process_message(message, reprocess=True)
		
	message in instances[instance]['held_messages'][key] = []
	#clear messages
	
def node_is_overtaken(instance, nodename):
	return nodename in instances[instance]['fault_list']		
	
def maybe_overtake_node(instance, nodename):
	if node_is_overtaken(instance, nodename):
		return True #node's already overtaken

	if len(instances[instance]['fault_list']) < fault_bound:
		instances[instance]['fault_list'].append(nodename) #node is now officially Adversarial	
		return True
	else:
		return False #we've taken over all the nodes we can

def get_uid(message):
	#UID format used to store changed messages
	return (dumps(rbid),message['raw'])
 


def maybe_change_message(message, new_body, only_if_node_already_overtaken=False):
	#only_if_node_already_overtaken is normally FALSE, which means the adversary will try and take over a node that's not already taken over.
	#if it's set to true, messages will only be changed once a node is already registered as overtaken.
	uid = get_uid(message)
	instance = get_message_ID(message)
	target_node = get_message_sender(message)

	if ( node_is_overtaken(instance, target_node) if only_if_node_already_overtaken else maybe_overtake_node(instance, target_node) ) :
		#node is already counted as overtaken, or we just subverted it. Change is OK if we haven't already changed this message differently.
		if uid in instances[instance]['changed_messages']:
			#this message has already been changed once. use the way we changed it first.
			message['body'] = instances[instance]['changed_messages'][uid]
			return message, False
		else:
			message['body'] = new_body
			instances[instance]['changed_messages'][uid] = new_body #record change
			return message, True
	else:
		#node IS NOT counted as overtaken, and we can't/won't overtake it. Return message without changes.
		return message, None
			
			


def process_message(message, reprocess=False):
	instance = get_message_ID(message)
	try:
		rbid = message['meta']['rbid']
		epoch = rbid[2][1]
		iteration = rbid[2][2]
		sender = rbid[0]
	except Exception:
		print err
		raise err
	
	maybe_setup_instance(instance)
		
	thisInstance = instances[instance]
		
	# next, check to see that the message isn't old. If it is old, we've stopped interfering with that iteration and we just let it go through.
	# might want to rewrite this later.
	
	if epoch < thisInstance['epoch']:
		return_message(message)
	if iteration < thisInstance['iteration']:
		return_message(message)
	if epoch > thisInstance['epoch']:
		hold_message(message, 'wave1') # lambda: thisInstance['epoch'] == epoch)
	if iteration > thisInstance['iteration']:
		hold_message(message, 'wave1') # lambda: thisInstance['iteration'] == iteration)
		
		
	#next, figure out what type of message it is.
	
	#if it is a BRACHA message, we maybe do something with it.
	
	#if it is a COIN message, then for now, we let it go.
	
	if message['body'][0] == MessageMode.bracha:
		#figure out what wave it is
		wave = message['body'][1]
		value = message['body'][2][0]
		
		if wave == 3:
			deciding = message['body'][2][1]
		#if it's wave one, let's check to see if we know what X node is sending out in wave one

		
		if instances[instance]['gameplan'] == 'shaker':
			return#TODO
			#Shaker doesn't affect content of messages, it just screws with timing.
			
		
		
		if wave != 1: #the adversary doesn't interfere with Wave 2+ bracha messages. It can get everything it wants by arranging the content and timing of wave 1 messages.
		#exception is for Lie Like A Rug, in which case it changes the values on its own nodes to match target, or just flip.
			if instances[instance]['gameplan'] != 'lie_like_a_rug':
				return_message(message)
				return
			else:
				#adversary prepares 
				updated_value = list(message['body'][2])
				updated_value[0] = (False if value else True) if instances[instance]['target_value'] is None else instances[instance]['target_value']
				updated_body = message['body'][:] #copy
				updated_body[2] = updated_value
				
				altered_message, _ = maybe_change_message(message, updated_body) #overwrite message, if possible
				return_message(altered_message)
				return
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

			if rbid[0] not in thisInstance['wave_one_bracha_values'][1 if value else 0]:
				thisInstance['wave_one_bracha_values'][1 if value else 0].append(rbid(0)) #store the node in the right bucket
			if len(thisInstance['wave_one_bracha_values'][0])+len(thisInstance['wave_one_bracha_values'][1]) < num_nodes:
				#hold message if everyone hasn't reported in 
				#yeah, yeah, I know. The adversary for a fault-tolerant system isn't fault-tolerant itself! It's ironic, isn't it?
				hold_message(message, lambda: len(thisInstance['wave_one_bracha_values'][0])+len(thisInstance['wave_one_bracha_values'][1]) == num_nodes)
			else: 
				
			
				
	
				if len(thisInstance['wave_one_bracha_values'])
	
	
				if instances[instance]['gameplan'] == 'split_vote':
		
		
				elif instances[instance]['gameplan'] == 'split_hold':
		
		
				elif instances[instance]['gameplan'] == 'force_decide':
		
				elif instances[instance]['gameplan'] == 'lie_like_a_rug':
		
		
	
	
	elif message['body'][0] == MessageMode.coin_flip or message['body'][0] == MessageMode.coin_list or message['body'][0] == MessageMode.coin_ack:
		return_message(message)
		return
		
		#return message, for now
	

def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	print "Starting up..."
	global username, num_nodes, fault_bound, all_nodes, instances
		
	
	username = args[0]
	with open(args[1]) as node_list:
		all_nodes = [line.rstrip() for line in node_list]
	
	MessageHandler.init_adversary()
	
	num_nodes = len(all_nodes)
	fault_bound = (num_nodes - 1) // 3  #t < n/3. Not <=.
	
	print "Maximum adversarial nodes: {}/{}.".format(fault_bound, num_nodes)
	
	weSaidNoMessages = False 
	while True:
		#print "Checking for messages."
		
		adv_message = MessageHandler.receive_backchannel()
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
