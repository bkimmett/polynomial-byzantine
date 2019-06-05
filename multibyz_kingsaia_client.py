#!/usr/bin/env python

from __future__ import division
from sys import argv, exit
from time import sleep
from string import split
import random
#from random import choice, sample, random
import multibyz_kingsaia_network as MessageHandler
#getting an error with the above line? 'pip install kombu'


# class MessageHandler:
# 
# 	connection = None
# 	producer = None
# 	consumer = None
# 	global_exchange = None
# 	my_queue = None
# 	recv_loop = None
# 	username = None
# 	
# 	#the message format I'm using:
# 	#(sender, mode, (supplemental info), data)
# 	#reliable broadcast:
# 	##(sender, "rBroadcast", phase, message, [debug info]) - message IS A TUPLE because it's used for dict hashing
# 	#INITIAL SENDER OF RBROADCAST SHOULD ADD A NONCE to avoid same message sent twice being ignored second time. A counter and its sender ID should be sufficient.
# 	#'sender' is assigned by the receiver module
# 	
# 	@classmethod
# 	def init(thisClass,username):
# 		thisClass.username = username
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
# 		thisClass.producer.publish(message,routing_key=str(destination)+'-q',headers={"type":"node","sender":thisClass.username})
# 		#in the real world, there would probably be a try(), and in the event of an error, a revive() and a reattempt.
# 		#also in the real world, the sender would be a property of the messages' transit. Here, using this networking framework, we have to add it manually.
# 		#for those testing adversarial nodes: assume they are unable to forge the 'sender' attribute.
# 		
# 		#MODULAR - replace this code with whatever network functionality.
# 		return
# 	
# 	@classmethod
# 	def sendAll(thisClass,message):
# 		thisClass.producer.publish(message,exchange=thisClass.global_exchange,headers={"type":"node",""sender":thisClass.username})
# 		#IMPORTANT: for reliable broadcast, "send to all" means yourself too.
# 		#MODULAR - replace this code with whatever network functionality.
# 		return
# 	
# 	@classmethod
# 	def receive_next(thisClass):
# 		#try: 
# 		message_ok = False
# 		while not message_ok:		
# 			message_ok = True
# 			message = thisClass.my_queue.get(True) #the 'True' means messages are auto-acknowledged and are not redelivered later if nothing is done about them. If I want to acknowledge a message manually, I'd use message.ack() and skip the 'True' in the get().
# 			#by the way: it's more proper to use message.decode() just so that data transfer is preserved - this means I can send python objects as messages.
# 			try:
# 				if message.headers['type'] != "client" and message.headers['type'] != "announce":
# 					message_ok = False
# 					pass 
# 					#ignore all internal messages - if we grabbed one, go back for another
# 			except: #if the message doesn't HAVE a 'type', do nothing and let it go through - it is almost certainly None, i.e. no message.
# 				pass
# 
# 		return message
# 		#MODULAR - replace this code with whatever network functionality.

def main(args):
	#args = my user ID, the number of nodes. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	print "Starting up..."
	
	global random_generator
	
	try:
		random_generator = random.SystemRandom()
	except Exception as e:
		print "Couldn't initialize RNG. Check that your OS/device supports random.SystemRandom()."
		print repr(e)
		exit()
	
	decision_IDs = {}
	
	#num_nodes = int(args[0])
	with open(args[0]) as node_list:
		all_nodes = [line for line in node_list]
	
	num_nodes = len(all_nodes)
	fault_bound = (num_nodes - 1) // 3  #t < n/3. Not <=.

	byz_ids_so_far = 0

	
	if len(args) > 1:
		MessageHandler.init(args[1],"client")
	else:
		MessageHandler.init("client","client") #anonymous client
		
	while True:	
		print "Checking for messages."
		while True:
			message = MessageHandler.receive_next()
			if message is None:
				weSaidNoMessages = True
				break
				#sleep(1) #wait a second before we check again.
			else:
				weSaidNoMessages = False
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
					print message.body
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
					
						if decision_IDs[byzID][2] == None and len(decision_IDs[byzID][1 if decision else 0]) >= fault_bound + 1:
							decision_IDs[byzID][2] = [True if decision else False]
							print "Accepting decision for byzantine ID {}: {}.",format(byzID, decision)
					
						if decision_IDs[byzID][3] == None and len(decision_IDs[byzID][1 if decision else 0]) >= num_nodes // 2:
							decision_IDs[byzID][3] = [True if decision else False]
							print "Received decision majority for byzantine ID {}: {}.",format(byzID, decision)	
						
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
					pass #malformed headers! Throw an error? Drop? Request resend?
				
			
		
				
		try:
			message = raw_input("Ready > ")
			if message != "":
				try:
					input_split = split(message," ",1)
					command = '' if len(input_split) < 1 else input_split[0]
					message2 = '' if len(input_split) < 2 else input_split[1]
							
					if command == "msg":
						dest, message3 = split(message2+" ", " ", 1)
						MessageHandler.send(message3[:-1],{'code':'broadcast'},dest)
						#send format: message, dest, meta
						print "Message sent to {}.".format(dest)
					elif command == "msgall":
						MessageHandler.sendAll(message2,{'code':'broadcast'})
						#send format: message, meta
						print "Message sent to everyone."
					elif command == "byz": 
						byz_ids_so_far += 1
						byz_id = "{}-{}".format("".join([random_generator.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in range(10)]),byz_ids_so_far)
						#gives a random ten-letter ID and a counter.
						
						input_split = split(message2," ",2)
						numTrue = 0 if len(input_split) < 1 else int(input_split[0])
						numFalse = num_nodes - numTrue if len(input_split) < 2 else int(input_split[1])
						
						numRandom = num_nodes - (numTrue + numFalse)
						
						print "Starting byzantine agreement instance {}, {} nodes True, {} nodes False{}.".format(byz_id,numTrue,numFalse,
						"" if numRandom == 0 else ", {} nodes random".format(numRandom))
						
						random_node_order = random_generator.sample(all_nodes,num_nodes)
						
						for node in random_node_order[:numTrue]:
							MessageHandler.send(True,{'code':'byzantine','byzID':byz_id},node)
							
						for node in random_node_order[numTrue:numTrue+numFalse]:
							MessageHandler.send(False,{'code':'byzantine','byzID':byz_id},node)	
							
						for node in random_node_order[numTrue+numFalse:]:
							MessageHandler.send(random_generator.random() >= .5,{'code':'byzantine','byzID':byz_id},node)	
						
						
						#MessageHandler.send(message3,dest,{'code':'broadcast'})
						#send format: message, meta, dest IN THAT ORDER!!!
						#print "Message sent to {}.".format(dest)
						
					elif command == "halt":
						print "Shutting down."
						exit(0)
					elif command == "help":
						print """Available commands:
msg <dest> <message> - send a message to one node; that node will reliable-broadcast it
msgall <message> - send a message to all nodes; each will reliable-broadcast it
	(node names for 'msg' and 'msgall' must not contain spaces.)
byz <nodes_true> <nodes_false> - start a byzantine agreement instance. <nodes_true> nodes will have the starting value 'True' (1), <nodes_false> nodes will have the starting value 'False' (0).
help - display this message
halt - shut down the client. If you're using the runner, this will stop all nodes."""
					else:
						print "Invalid command."
				except ValueError:
					print "Error reading command."
		except KeyboardInterrupt:
			print
			print "Shutting down."
			exit(0)

		
if __name__ == "__main__":
    main(argv[1:])	