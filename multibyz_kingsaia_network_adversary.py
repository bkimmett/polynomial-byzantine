from kombu import Connection, Queue, Exchange #, Producer, Consumer
#from kombu.common import drain_consumer
#getting an error with the above line? 'pip install kombu'

### WHAT'S UP WITH THIS FILE? 
# This file is a variant version of the network library that's used for simulating an adversarial influence on a Byzantine Agreement attempt. It adds additional functions that establish a backchannel to the adversary, used for adversarial filtering/delay of network traffic, and methods for sending from and thereto.

__connection = None
__producer = None
#__consumer = None
__global_exchange = None
__my_queue = None
#__recv_loop = None
__username = None
__my_type = None

__backchannel = None
__backch_producer = None
__adv_exchange = None
__adv_queue = None


#the message format I'm using:
#(sender, mode, (supplemental info), data)
#reliable broadcast:
##(sender, "rBroadcast", phase, message, [debug info]) - message IS A TUPLE because it's used for dict hashing
#INITIAL SENDER OF RBROADCAST SHOULD ADD A NONCE to avoid same message sent twice being ignored second time. A counter and its sender ID should be sufficient.
#'sender' is assigned by the receiver module

def init(username, msgtype):
	global __username, __my_type, __connection, __global_exchange, __producer, __my_queue, __backchannel, __backch_producer, __adv_exchange, __adv_queue
	__username = username
	__my_type = msgtype
	print "Username: "+username
	__connection = Connection('amqp://') #that should be enough, right?
	__connection.connect() #set up NOW
	#channel = connection.channel()
	__global_exchange = Exchange('broadcast', type='fanout', durable=False, delivery_mode=1) #the 1 means messages are cleared if the server is restarted. For testing purposes.
	__global_exchange.maybe_bind(__connection) #this should prevent the same exchange from being bound twice by multiple nodes. I think.
	__producer = __connection.Producer(__connection)
	__my_queue = Queue(username+'-q', exchange=__global_exchange, routing_key=username+'-q')
	__my_queue = __my_queue(__connection)
	__my_queue.declare()
	#print "Q:"
	#print __my_queue
	#__consumer = __connection.Consumer(queues=__my_queue) #we're not using consumer 'cause we're using queue get
	
	#__recv_loop =  drain_consumer(__consumer, timeout=1)
	
	__backchannel = Connection('amqp://')
	__backchannel.connect()
	__adv_exchange = Exchange('adversary', durable=False, delivery_mode=1)
	__adv_exchange.maybe_bind(__backchannel)
	__backch_producer = __backchannel.Producer(__backchannel)
	__adv_queue = Queue(username+'-adv', exchange=__adv_exchange, routing_key=username+'-adv')
	__adv_queue = __adv_queue(__backchannel)
	__adv_queue.declare()


def init_adversary():
	global  __username, __my_type, __connection, __global_exchange, __producer,  __backchannel, __backch_producer, __adv_exchange, __adv_queue #, __my_queue
	
	__username = 'adversary'
	__my_type = 'adversary'
	
	#adversary has broadcast-only access to the regular exchange
	__connection = Connection('amqp://') 
	__connection.connect()
	__global_exchange = Exchange('broadcast', type='fanout', durable=False, delivery_mode=1)
	__global_exchange.maybe_bind(__connection) 
	__producer = __connection.Producer(__connection)
	
	__backchannel = Connection('amqp://')
	__backchannel.connect()
	__adv_exchange = Exchange('adversary', durable=False, delivery_mode=1)
	__adv_exchange.maybe_bind(__backchannel)
	__backch_producer = __backchannel.Producer(__backchannel)
	__adv_queue = Queue('adversary', exchange=__adv_exchange, routing_key='adversary')
	__adv_queue = __adv_queue(__backchannel)
	__adv_queue.declare()

		
		
	
def shutdown():
	__connection.release()
	__backchannel.release()	
	
	

def send(message,metadata,destination,type_override=None):
	__producer.publish(message,routing_key=str(destination)+'-q',headers={"type": type_override if type_override is not None else __my_type,"sender":__username,"meta":metadata}, serializer='json')


	#in the real world, there would probably be a try(), and in the event of an error, a revive() and a reattempt.
	#also in the real world, the sender would be a property of the messages' transit. Here, using this networking framework, we have to add it manually.
	#for those testing adversarial nodes: assume they are unable to forge this 'sender' attribute.
	
	#MODULAR - replace this code with whatever network functionality.
	return


def sendAsAdversary(message,metadata,destination):
	#sends back filtered message from adversary to be accepted.
	__backch_producer.publish(message,routing_key=str(destination)+'-adv',headers={"meta":metadata}, serializer='json')
	
def adversaryBroadcast(message,metadata,sender='adversary',type_override=None):
	__producer.publish(message, exchange=__global_exchange, headers={"type":type_override if type_override is not None else 'node',"sender":sender,"meta":metadata}, serializer='json')

def sendToAdversary(message,metadata,type_override=None):
	#sends message to adversary for value messing-with..
	__backch_producer.publish(message, routing_key="adversary", exchange=__adv_exchange, headers={"type":type_override if type_override is not None else __my_type,"sender":__username,"meta":metadata}, serializer='json')

#def sendToAdversary2(message,metadata,type_override=None):
	#sends message about to be accepted to adversary.
#	__backch_producer.publish(message, routing_key="adversary-accept", exchange=__adv_exchange, headers={"type":type_override if type_override is not None else __my_type,"sender":__username,"meta":metadata}, serializer='json')


def sendAll(message,metadata,type_override=None):
	__producer.publish(message, exchange=__global_exchange, headers={"type":type_override if type_override is not None else __my_type,"sender":__username,"meta":metadata}, serializer='json')
	#IMPORTANT: for reliable broadcast, "send to all" means yourself too.
	#MODULAR - replace this code with whatever network functionality.
	return
	
	
def receive_backchannel(im_adversary=False):	
	#receive adversarial traffic.
	#code = None
	message = __adv_queue.get(True)
	if message is not None:
		try:
			if message.headers['type'] == 'node':
				code = 'value'
			else:
				code = message.headers['type'] #used for 'timing' and others
		except Exception as e:
			print "Something went wrong with backchannel message decoding. Message:"
			print repr(message)
			print "Body: "+repr(message.body)
			print "Headers: "+repr(message.headers)
			print "Error: "+repr(e)
			return None
	if message is None:
		return None
	try:
		return {'body': message.decode(), 'type': message.headers['type'], 'sender': message.headers['sender'], 'meta': message.headers['meta'], 'raw': message.body, 'code': code}
	except Exception as e:
		print "Something went wrong with backchannel message receiving. Message:"
		print repr(message)
		print "Body: "+repr(message.body)
		print "Headers: "+repr(message.headers)
		print "Error: "+repr(e)
		return None
	

def receive_next():
	message = __my_queue.get(True) #the 'True' means messages are auto-acknowledged and are not redelivered later if nothing is done about them. If I want to acknowledge a message manually, I'd use message.ack() and skip the 'True' in the get().
	#by the way: it's more proper to use message.decode() just so that data transfer is preserved - this means I can send python objects as messages.	
	#receiving should NOT ignore messages from oneself. This is required for reliable broadcast.
	if message is None:
		return None
	try:
		return {'body': message.decode(), 'type': message.headers['type'], 'sender': message.headers['sender'], 'meta': message.headers['meta'], 'raw': message.body}
	except Exception as e:
		print "Something went wrong with message receiving. Message:"
		print repr(message)
		print "Body: "+repr(message.body)
		print "Headers: "+repr(message.headers)
		print "Error: "+repr(e)
		return None
	#MODULAR - replace this code with whatever network functionality.
