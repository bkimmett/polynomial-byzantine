#!/usr/bin/env python

from __future__ import division
from math import log, ceil
from itertools import permutations
from random import sample
from subprocess import Popen, call
from os import mkdir
from sys import argv
import multibyz_kingsaia_network_adversary as MessageHandler

def main(args):
	#args = number of nodes.
	print "Starting up..."
		
	num_nodes = int(args[0])
		
	node_names = ['node{}_{}'.format(i+1,key) for i, key in enumerate(sample(["".join(item) for item in permutations('ABCDEFGHIJKLMNOPQRSTUVWXYZ', ceil(log(num_nodes, 26))+1)], num_nodes))]
	#make a list of node names, in the form 'node1_CZY' where the bit after the underscore is a randomized tag, unique within this run. As many letters after the underscore will be used as necessary for all combinations to have a unique tag.
	
	#write node list
	with open('multibyz_kingsaia_nodenames','w') as thisFile:
		for name in node_names:
			thisFile.write(name+'\n')
	
	#make logs dir
	try:
		mkdir('logs/')
	except OSError:
		pass #dir already exists
	
	#server needs to be launched manually, with command 'rabbitmq-server &'
	
	#launch nodes
	for node in node_names:
		print "Starting {}.".format(node)
		Popen(['python', 'multibyz_kingsaia_node_adversary.py', node, 'multibyz_kingsaia_nodenames'], stdout=open('logs/log_'+node+'.txt','a',0) ) #stderror resolves on to this stdout. the '0' at the end makes all writes to log files immediate.
		
	#launch client
	#maybe this gets done manually for UI?
	print "Don't forget to run the adversary separately, 'K?"
	try:
		call(['python', 'multibyz_kingsaia_client_adversary.py', 'multibyz_kingsaia_nodenames'])
	except (KeyboardInterrupt, SystemExit):
		pass #swallow Ctrl-C and graceful halt
		#'call' instead of 'Popen' means this will WAIT for the process to return.
	
		#after this point, we're done, and are doing shutdown.
	
		#halt all
	MessageHandler.init("HaltHandler","halt") #anonymous client
	MessageHandler.sendAll(None,None) #send empty halt message
	
		#halt server also needs to be done manually. Or you can leave it up for when you go again.
	
if __name__ == "__main__":
	main(argv[1:])	