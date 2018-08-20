#!/usr/bin/env python

from __future__ import division
from sys import argv
from time import sleep
import multibyz_kingsaia_network as MessageHandler
#getting an error with the above line? 'pip install kombu'
from enum import Enum
#getting an error with the above line? 'pip install enum34'

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

# class MessageHandler:
# 
# 	connection = None
# 	producer = None
# 	consumer = None
# 	global_exchange = None
# 	my_queue = None
# 	recv_loop = None
# 	username = None
# 	myType = None
# 	
# 	#the message format I'm using:
# 	#(sender, mode, (supplemental info), data)
# 	#reliable broadcast:
# 	##(sender, "rBroadcast", phase, message, [debug info]) - message IS A TUPLE because it's used for dict hashing
# 	#INITIAL SENDER OF RBROADCAST SHOULD ADD A NONCE to avoid same message sent twice being ignored second time. A counter and its sender ID should be sufficient.
# 	#'sender' is assigned by the receiver module
# 	
# 	@classmethod
# 	def init(thisClass,username, type):
# 		thisClass.username = username
# 		thisClass.myType = type
# 		print "Username: "+username
# 		thisClass.connection = Connection('amqp://') #that should be enough, right?
# 		thisClass.connection.connect(); #set up NOW
# 		#channel = connection.channel()
# 		thisClass.global_exchange = Exchange('broadcast', type='fanout');
# 		thisClass.global_exchange.maybe_bind(thisClass.connection) #this should prevent the same exchange from being bound twice by multiple nodes. I think.
# 		thisClass.producer = thisClass.connection.Producer(thisClass.connection)
# 		thisClass.my_queue = Queue(username+'-q', exchange=thisClass.global_exchange, routing_key=username+'-q')
# 		thisClass.my_queue = thisClass.my_queue(thisClass.connection)
# 		thisClass.my_queue.declare()
# 		print thisClass.my_queue
# 		#consumer = connection.Consumer(connection, my_queue)
# 		thisClass.consumer = thisClass.connection.Consumer(queues=thisClass.my_queue)
# 		
# 		thisClass.recv_loop =  drain_consumer(thisClass.consumer, timeout=1)
# 		
# 	@classmethod
# 	def send(thisClass,message,destination):
# 		thisClass.producer.publish(message,routing_key=str(destination)+'-q',headers={"type":thisClass.myType,"sender":thisClass.username})
# 		#in the real world, there would probably be a try(), and in the event of an error, a revive() and a reattempt.
# 		#also in the real world, the sender would be a property of the messages' transit. Here, using this networking framework, we have to add it manually.
# 		#for those testing adversarial nodes: assume they are unable to forge the 'sender' attribute.
# 		
# 		#MODULAR - replace this code with whatever network functionality.
# 		return
# 	
# 	@classmethod
# 	def sendAll(thisClass,message):
# 		thisClass.producer.publish(message,exchange=thisClass.global_exchange,headers={"type":thisClass.myType,"sender":thisClass.username})
# 		#IMPORTANT: for reliable broadcast, "send to all" means yourself too.
# 		#MODULAR - replace this code with whatever network functionality.
# 		return
# 	
# 	@classmethod
# 	def receive_next(thisClass):
# 		#try: 
# 		#message_ok = False
# 		#while not message_ok:		
# 			#message_ok = True
# 		message = thisClass.my_queue.get(True) #the 'True' means messages are auto-acknowledged and are not redelivered later if nothing is done about them. If I want to acknowledge a message manually, I'd use message.ack() and skip the 'True' in the get().
# 			#by the way: it's more proper to use message.decode() just so that data transfer is preserved - this means I can send python objects as messages.
# 			#if message is not None:
# 			#	pass
# 				#check validity if something found
# 				#receiving should NOT ignore messages from oneself. This is required for reliable broadcast.
# 
# 		return message
# 		#MODULAR - replace this code with whatever network functionality.
		
username = None
num_nodes = 0
fault_bound = 0
message_counter = 0
		
class ReliableBroadcast:
	
	broadcasting_echoes = {}
	
	#timeout protocol: set most recent update time and if that times out without broadcast completing, we junk it.
	
	
	#if receiving receives a message from a node not currently in the network, it should store that in case of that node joining later (and the join being late).
	
	@classmethod
	def setupRbroadcastEcho(thisClass,data):
		thisClass.broadcasting_echoes[data] = [False, set(), set(), 1] #no initial received, no echoes received, no readies received, Phase no. 1
		print "Setting up broadcast tracking entry for key < {} >.".format(repr(data))
	
	#metadata format:
	#every message is either a client message or node (reliable broadcast) message or node (manual) message.
	#client messages can have whatever metadata they damn well please, ignore them for now.
	#node messages metadata: (phase, RBID)
	#phase - indicates whether this is a reliable broadcast message or not. Possible values include:
		## "initial", "echo", "ready" - part of reliable.
		## "direct" - NOT part of reliable.
		## TODO - change these to enums later.
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
	def broadcast(thisClass,message):
		global message_counter
		MessageHandler.sendAll(("rBroadcast","initial",(username, message_counter, message),None),("rBroadcast","initial",username, message_counter,)) 
		print "SENDING INITIAL reliable broadcast message for key < {} > to all.".format(repr(message))
		message_counter += 1
		#We don't need to call setupRbroadcastEcho yet. The first person to receive the 'initial' message will be-- us! And it'll happen then.
	
	
	@classmethod
	def handleRBroadcast(thisClass,message):
		
		sender = message.headers['sender'] #error?: malformed data
		_, phase, data, debuginfo = message.decode() #first var is used for type, skip that
		
		data = tuple(data) #bug fix: for some reason tuples are decoded into lists upon receipt. No idea why.
		
		if data not in thisClass.broadcasting_echoes:
			thisClass.setupRbroadcastEcho(data) #TODO: A concern is that a spurious entry could be created after [A] a finished entry is removed and a message arrives late, [B] a malformed entry arrives [C] a malicious entry arrives. In the real world, is there a timeout for rbroadcast pruning? (something on the line of a day to a week, something REALLY BIG) How much storage space for rbroadcast info do we HAVE, anyway?
			
			#there's also the concern that if a node shuts down (unexpectedly?) it loses all broadcast info. Could be resolved by just counting that node towards the fault bound OR semipersistently storing broadcast info.
		
		#TODO: Security measure. If an Initial message says (in the UID) it is from sender A, and the sender data says it is from sender B, throw an exception based on security grounds. Maybe dump that message. Effectively, that node is acting maliciously.
		#This is only applicable once we move away from prototype code.
		
		#by using sets of sender ids, receiving ignores COPIES of messages to avoid adversaries trying to pull a replay attack.
	
		
		if phase == "initial":
			thisClass.broadcasting_echoes[data][0] = True #initial received!!
			print "Received INITIAL reliable broadcast message for key < {} > from node {}.".format(repr(data),sender)
		elif phase == "echo":
			thisClass.broadcasting_echoes[data][1].add(sender)
			print "Received ECHO reliable broadcast message for key < {} > from node {}.".format(repr(data),sender)
			if thisClass.broadcasting_echoes[data][3] == 1 or thisClass.broadcasting_echoes[data][3] == 2:
				print "{}/{} of {} echo messages so far.".format(len(thisClass.broadcasting_echoes[data][1]), (num_nodes + fault_bound) / 2, num_nodes) #print how many echoes we need to advance
			else:
				print "{} of {} echo messages.".format(len(thisClass.broadcasting_echoes[data][1]), num_nodes) #just print how many echoes
		elif phase == "ready":
			thisClass.broadcasting_echoes[data][2].add(sender)
			print "Received READY reliable broadcast message for key < {} > from node {}.".format(repr(data),sender)
			if thisClass.broadcasting_echoes[data][3] == 1 or thisClass.broadcasting_echoes[data][3] == 2:
				print "{}/{} of {} ready messages so far.".format(len(thisClass.broadcasting_echoes[data][2]), fault_bound + 1, num_nodes) #print how many readies we need to advance
			elif thisClass.broadcasting_echoes[data][3] == 3:
				print "{}/{} of {} ready messages so far.".format(len(thisClass.broadcasting_echoes[data][2]), fault_bound*2 + 1, num_nodes) #print how many readies we need to accept
			else: 
				print "{} of {} ready messages.".format(len(thisClass.broadcasting_echoes[data][2]), num_nodes) #print how many readies we got
		else:
			print "Received invalid reliable broadcast message from node {} ().".format(sender,phase)
			pass #error!: throw exception for malformed data
			
		return thisClass.checkRbroadcastEcho(data) #runs 'check message' until it decides we're done handling any sort of necessary sending
	
	@classmethod
	def checkRbroadcastEcho(thisClass,data):
		
		#TODO: A concern - (num_nodes + fault_bound) / 2 on a noninteger fault_bound?
					
		if thisClass.broadcasting_echoes[data][3] == 1:
			#waiting to send echo
			if thisClass.broadcasting_echoes[data][0] or len(thisClass.broadcasting_echoes[data][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[data][2]) >= fault_bound + 1: #one initial OR (n+t)/2 echoes OR t+1 readies
				#ECHO!
				print "SENDING ECHO reliable broadcast message for key < {} > to all.".format(repr(data))
				MessageHandler.sendAll(("rBroadcast","echo",data,None)) 
				#4th item in message is debug info
				thisClass.broadcasting_echoes[data][3] = 2 #update node phase
			else:
				return #have to wait for more messages
				
		if thisClass.broadcasting_echoes[data][3] == 2:
			#waiting to send ready
			if len(thisClass.broadcasting_echoes[data][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[data][2]) >= fault_bound + 1: #(n+t)/2 echoes OR t+1 readies
				#READY!
				print "SENDING READY reliable broadcast message for key < {} > to all.".format(repr(data))
				MessageHandler.sendAll(("rBroadcast","ready",data,None)) #message format: type, [phase, data, debuginfo]
				thisClass.broadcasting_echoes[data][3] = 3 #update node phase
			else:
				return #have to wait for more messages
				
		if thisClass.broadcasting_echoes[data][3] == 3:
			#waiting to accept
			if len(thisClass.broadcasting_echoes[data][2]) >= fault_bound*2 + 1: #2t+1 readies only
				#ACCEPT!
				thisClass.broadcasting_echoes[data][3] = 4
				return thisClass.acceptRbroadcast(data)
			else:
				return #wait for more messages!
		
		if thisClass.broadcasting_echoes[data][3] == 4:
			return #we've already accepted this. no further processing.
		else:
			pass #error! throw exception for malformed data in here. How'd THIS happen?			

	
	@classmethod
	def acceptRbroadcast(thisClass,data):	
		return data	
		pass
		#what does accepting a r-broadcasted message LOOK like? Well, the message is confirmed to be broadcast, and is passed on to the other parts of the program.
		
		#what in Byzantine uses RB:
		
		#what in Byzantine doesn't:
		
		
		
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

			type = message.headers['type']
			
			msgBody = message.decode()
			
			if type == "client":
				#TODO - client messages.
				code = msgBody[0]
				if code == "broadcast":
					print "Client message received: broadcast {}.".format(repr(msgBody[1]))
					ReliableBroadcast.broadcast(msgBody[1])
				else:
					print "Unknown client message received - code: {}.".format(msgBody[0])
					print message.headers
					print message.body
					pass #no other types of client messages implemented yet.
			
			elif type == "node":
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