#!/usr/bin/env python

from __future__ import division
from sys import argv
from time import sleep
import multibyz_kingsaia_network as MessageHandler
#getting an error with the above line? 'pip install kombu'

# ADVERSARY 'spaniel' - reacts excitedly to every reliable broadcast message. Still accepts things on normal criteria.
# might change to always accept on receiving a 'ready' later.
		
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
	
	@classmethod
	def broadcast(thisClass,message):
		global message_counter
		MessageHandler.sendAll(("rBroadcast","initial",(username, message_counter, message),None))
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
			print "SENDING ECHO reliable broadcast message for key < {} > to all.".format(repr(data))
			MessageHandler.sendAll(("rBroadcast","echo",data,None)) #ADVERSARY - woof woof!
		elif phase == "echo":
			thisClass.broadcasting_echoes[data][1].add(sender)
			print "Received ECHO reliable broadcast message for key < {} > from node {}.".format(repr(data),sender)
			if thisClass.broadcasting_echoes[data][3] == 1 or thisClass.broadcasting_echoes[data][3] == 2:
				print "{}/{} of {} echo messages so far.".format(len(thisClass.broadcasting_echoes[data][1]), (num_nodes + fault_bound) / 2, num_nodes) #print how many echoes we need to advance
			else:
				print "{} of {} echo messages.".format(len(thisClass.broadcasting_echoes[data][1]), num_nodes) #just print how many echoes
			print "SENDING READY reliable broadcast message for key < {} > to all.".format(repr(data))
			MessageHandler.sendAll(("rBroadcast","ready",data,None)) #ADVERSARY - woof woof!
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
				
				#4th item in message is debug info
				thisClass.broadcasting_echoes[data][3] = 2 #update node phase
			else:
				return #have to wait for more messages
				
		if thisClass.broadcasting_echoes[data][3] == 2:
			#waiting to send ready
			if len(thisClass.broadcasting_echoes[data][1]) >= (num_nodes + fault_bound) / 2 or len(thisClass.broadcasting_echoes[data][2]) >= fault_bound + 1: #(n+t)/2 echoes OR t+1 readies
				#READY!
	
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
	print "I'm an adversary! Class: SPANIEL (responds to every reliable broadcast message, thresholds or not)"

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