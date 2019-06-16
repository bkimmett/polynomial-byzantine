#!/usr/bin/env python

#It's a lot like a firewall with deep packet inspection, really. Except mean.

# A NOTE ON HOW THE ADVERSARY IS SIMULATED

# All of the communications of the implementation use Reliable Broadcast. Which is remarkably difficult to interfere with... which is kind of the point. So, to simulate it, we have each node add an extra step before it accepts a Reliable Broadcast message.
# The extra step is: the node sends its ID, along with the message it was about to accept, to the simulated adversary. The simulated adversary can choose to return it now (indicating no delay), return it later (indicating delay), or change it (which means the adversary has taken over the original sender of the node and now can broadcast whatever it wants, but is pretending to be normal)




#SETUP:

# set up backchannel

# set up node list, alter quota
















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

# then make sure the nodes you want to hold (less than 2t) get enough 'False' wave 2s to send a deciding wave 3 message as 'False'. Then make sure the rest don't change their vote. Then, have all the deciding messages get from point A to point B on the nodes you want to hold.



# FORCE DECIDE:	set all nodes to 'False' in wave 2 and sit back and watch the fireworks.