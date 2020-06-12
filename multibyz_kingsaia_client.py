#!/usr/bin/env python
# pylint: disable=mixed-indentation,trailing-whitespace,bad-whitespace,line-too-long,invalid-name

from __future__ import division
from sys import argv, exit
from time import time #, sleep
from string import split
import random
import threading
import multibyz_kingsaia_network_adversary as MessageHandler
#getting an error with the above line? 'pip install kombu'

def check_for_messages_loop(timeout):
	print "Checking for messages."
		while True:
			#if time() - last_message_time >= 5:
			#	break #if we've been processing messages for 5 seconds straight, pause to give control to the user
			#message = MessageHandler.receive_next()
			if message is None:
				#weSaidNoMessages = True
				#break
				sleep(timeout) #wait a second before we check again.
			else:
				#weSaidNoMessages = False
				
				#debug: print message info
				#print message.headers
				#print message.body
				#print repr(message)
				#type = message['type']
			
				if message['type'] == "client":
					pass #We sent this message. Ignore it.
				elif message['type'] == "node":
					pass #IGNORE - internal message
				elif message['type'] == "announce":
					print "Announcement to client: "
					print message['body']
				elif message['type'] == "decide":
					#We're assuming the adversary won't misformat decide messages.
					byzID = message['meta']
					if byzID not in decision_IDs:
						decision_IDs[byzID] = [[],[],None,None]
					sender = message['sender']
					decision = message['body']
					if sender not in decision_IDs[byzID][1 if decision else 0]:
						print "Received deciding message from node {} for byzantine ID {}: {}.".format(sender, byzID, decision)
						decision_IDs[byzID][1 if decision else 0].append(sender)
					
						if decision_IDs[byzID][2] is None and len(decision_IDs[byzID][1 if decision else 0]) >= fault_bound + 1:
							decision_IDs[byzID][2] = [True if decision else False]
							print "Accepting decision for byzantine ID {}: {}.".format(byzID, decision)
					
						if decision_IDs[byzID][3] is None and len(decision_IDs[byzID][1 if decision else 0]) >= num_nodes // 2 + 1:
							decision_IDs[byzID][3] = [True if decision else False]
							print "Received decision majority for byzantine ID {}: {}.".format(byzID, decision)	
						
							if decision_IDs[byzID][2] != decision_IDs[byzID][3]:
								print "Warning: Majority and accepted decision don't match!"
					
					else:
						print "Duplicate deciding message received from node {}.".format(sender)
					
				elif message['type'] == "halt":
					#this is for local-machine testing purposes only - it makes every node exit. Assume the adversary can't do this.
					#exit(0)	
					pass
				else: 
					print "Unknown message received."
					print repr(message)
					#malformed headers! Throw an error? Drop? Request resend?
	


def main(args): #pylint: disable=too-many-locals, too-many-branches, too-many-statements
	#args = a list of node names of everyone participating, followed by a custom username if any
	print "Starting up..."
	
		
	try:
		random_generator = random.SystemRandom()
	except NotImplementedError:
		print "Couldn't initialize RNG. Check that your OS/device supports random.SystemRandom()."
		exit()
	
	decision_IDs = {}
	
	with open(args[0]) as node_list:
		all_nodes = [line.rstrip() for line in node_list]
	
	num_nodes = len(all_nodes)
	fault_bound = (num_nodes - 1) // 3  #t < n/3. Not <=.

	byz_ids_so_far = 0
	
	if len(args) > 1:
		MessageHandler.init(args[1],"client")
	else:
		MessageHandler.init("client","client") #anonymous client
		
	receive_thread = threading.Thread(target=check_for_messages_loop, args=(5,))
	receive_thread.daemon = True #background thread - cleared when program exits without needing to stop it manually
	receive_thread.start()	#message receipt will now happen in the background
		
	while True:	#pylint: disable=too-many-nested-blocks		
		try:
			message = raw_input("Ready > ")
			if message != "":
				try:
					input_split = split(message," ",1)
					command = '' if (not input_split) else input_split[0]
					message2 = '' if len(input_split) < 2 else input_split[1]
							
					if command == "msg":
						dest, message3 = split(message2+" ", " ", 1)
						MessageHandler.send(message3[:-1],{'code':'message'},dest)
						#send format: message, meta, dest
						print "Message sent to {}.".format(dest)
					elif command == "msgall":
						MessageHandler.sendAll(message2,{'code':'message'})
						#send format: message, meta
						print "Message sent to everyone."
					elif command == "rb":
						dest, message3 = split(message2+" ", " ", 1)
						MessageHandler.send(message3[:-1],{'code':'broadcast'},dest)
						#send format: message, meta, dest
						print "Message sent to {} to be broadcast.".format(dest)
					elif command == "adv" or command == "adv_get" or command == "adv_release":
						print "This isn't the adversarial-setup version of the client. Try another command."
					elif command == "byz": 
						byz_ids_so_far += 1
						byz_id = "{}-{}".format("".join([random_generator.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(10)]),byz_ids_so_far)
						#gives a random ten-letter ID and a counter.
						
						input_split = split(message2," ",2) #num_nodes_true, [num_nodes_false], leftovers
						numTrue = num_nodes if (not input_split) else int(input_split[0])
						numFalse = num_nodes - numTrue if len(input_split) < 2 else int(input_split[1])
						
						numRandom = num_nodes - (numTrue + numFalse)
						
						print "Starting byzantine agreement instance {}, {} nodes True, {} nodes False{}.".format(byz_id, numTrue, numFalse, "" if numRandom == 0 else ", {} nodes random".format(numRandom))
						
						random_node_order = random_generator.sample(all_nodes,num_nodes)
						
						print "Nodes true: {}".format(random_node_order[:numTrue])
						print "Nodes false: {}".format(random_node_order[numTrue:numTrue+numFalse])

						rand_nodes_true = []
						rand_nodes_false = []
						
						for node in random_node_order[:numTrue]:
							MessageHandler.send(True,{'code':'byzantine','byzID':byz_id},node)
							
						for node in random_node_order[numTrue:numTrue+numFalse]:
							MessageHandler.send(False,{'code':'byzantine','byzID':byz_id},node)	
							
						for node in random_node_order[numTrue+numFalse:]:
							flip = (random_generator.random() >= .5)
							MessageHandler.send(flip,{'code':'byzantine','byzID':byz_id},node)
							
							if flip:
								rand_nodes_true.append(node)
							else:
								rand_nodes_false.append(node)
						
						if not random_node_order[numTrue+numFalse:]: #checks if this portion is empty
							print "RNG Nodes true: {}".format(rand_nodes_true)
							print "RNG Nodes false: {}".format(rand_nodes_false)
						
						
						#send format: message, meta, dest IN THAT ORDER!!!
						#print "Message sent to {}.".format(dest)
						
					elif command == "halt":
						print "Shutting down."
						MessageHandler.shutdown()
						exit(0)
					elif command == "help":
						print """Available commands:
msg <dest> <message> - send a message to one node; that node will print it
msgall <message> - send a message to all nodes; each will print it
rb <dest> <message> - send a message to one node; that node will reliable-broadcast it
	(node names for 'msg', 'msgall', and 'rb' must not contain spaces.)
byz [<nodes_true> [<nodes_false>]] - start a byzantine agreement instance. 
	<nodes_true> nodes will have the starting value 'True' (1), <nodes_false> nodes will have the starting value 'False' (0). 
	If you only include <nodes_true>, the other nodes will start False. If you include both values but there are nodes left over, the remaining nodes will be assigned randomly.
help - display this message
halt - shut down the client. If you're using the runner, this will stop all nodes."""
					else:
						print "Invalid command."
				except ValueError:
					print "Error reading command."
		except KeyboardInterrupt:
			print
			print "Shutting down."
			MessageHandler.shutdown()
			exit(0)

		
if __name__ == "__main__":
	main(argv[1:])	
	