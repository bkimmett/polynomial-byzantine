#!/usr/bin/env python

from __future__ import division
from sys import argv
from time import sleep
from string import split
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
	if len(args) > 0:
		MessageHandler.init(args[0],"client")
	else:
		MessageHandler.init("client","client") #anonymous client
	while True:
		print "Checking for messages."
		message = MessageHandler.receive_next()
		if message is None:
			weSaidNoMessages = True
			sleep(1) #wait a second before we check again.
		else:
			weSaidNoMessages = False
			#print message.headers
			#print message.body

			type = message.headers['type']
			
			if type == "client":
				pass #We sent this message. Ignore it.
			elif type == "node":
				pass #IGNORE - internal message
			elif type == "announce":
				print "Announcement to client: "
				print message.body
				#announce to client - IGNORE
				pass
			else: 
				print "Unknown message received."
				print message.headers
				print message.body
				pass #malformed headers! Throw an error? Drop? Request resend?
				
			
				

		message = raw_input("Ready to send a client request - enter a destination, '::', message. > ")
		if message != "":
			try:
				dest, message2 = split(message,"::",1)
				dest = int(dest)
				MessageHandler.send(("broadcast",message2),dest)
				print "Message sent to "+str(dest)+"."
			except ValueError:
				MessageHandler.sendAll(("broadcast",message))
				print "Message sent to all nodes."

		
if __name__ == "__main__":
    main(argv[1:])	