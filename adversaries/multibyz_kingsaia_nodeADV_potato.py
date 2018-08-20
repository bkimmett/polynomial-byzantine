#!/usr/bin/env python

from __future__ import division
from sys import argv
from time import sleep
import multibyz_kingsaia_network as MessageHandler
#getting an error with the above line? 'pip install kombu'

# ADVERSARY 'potato' - receives messages but does nothing else. 

username = None
num_nodes = 0
fault_bound = 0
message_counter = 0

def main(args):
	#args = [[my user ID, the number of nodes]]. For the time being, we're not passing around node IDs but eventually we WILL need everyone to know all the node ids.
	print "Starting up..."
	global username, num_nodes, fault_bound
	username = args[0]
	MessageHandler.init(username,"node")
	num_nodes = int(args[1])
	fault_bound = num_nodes // 3 - 1 if num_nodes % 3 == 0 else num_nodes // 3 #t < n/3. Not <=.
	print "Maximum adversarial nodes: {}/{}.".format(fault_bound, num_nodes)
	print "I'm an adversary! Class: POTATO (does nothing)"
	weSaidNoMessages = False 
	while True:
		#print "Checking for messages."
		message_counter = 0
		message = MessageHandler.receive_next()
		while message is not None:
			message_counter += 1
			message = MessageHandler.receive_next()
			
		if message_counter > 0:
			print "{} messages received, but I am merely a potato.".format(message_counter)
			message_counter = 0
		sleep(1)
			
if __name__ == "__main__":
    main(argv[1:])	