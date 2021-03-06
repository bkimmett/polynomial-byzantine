# pylint: disable=mixed-indentation,trailing-whitespace,bad-whitespace,line-too-long,invalid-name, missing-docstring

from kombu import Connection, Queue, Exchange #, Producer, Consumer
#from kombu.common import drain_consumer
#getting an error with the above line? 'pip install kombu'

__connection = None
__producer = None
#__consumer = None
__global_exchange = None
__my_queue = None
#__recv_loop = None
__username = None
__my_type = None

#the message format I'm using:
#(sender, mode, (supplemental info), data)
#reliable broadcast:
##(sender, "rBroadcast", phase, message, [debug info]) - message IS A TUPLE because it's used for dict hashing
#INITIAL SENDER OF RBROADCAST SHOULD ADD A NONCE to avoid same message sent twice being ignored second time. A counter and its sender ID should be sufficient.
#'sender' is assigned by the receiver module

def init(username, msgtype):
	global __username, __my_type, __connection, __global_exchange, __producer, __my_queue
	__username = username
	__my_type = msgtype
	print "Username: "+username
	__connection = Connection('amqp://') #that should be enough, right?
	__connection.connect() #set up NOW
	#channel = connection.channel()
	__global_exchange = Exchange('broadcast', type='fanout', durable=False, delivery_mode=1) #the 1 means messages are cleared if the server is restarted. For testing purposes.
	__global_exchange.maybe_bind(__connection) #this should prevent the same exchange from being bound twice by multiple nodes. I think.
	__producer = __connection.Producer(__connection)
	__my_queue = Queue(username+'-q', exchange=__global_exchange, routing_key=username+'-q', durable=False) #set durable=True at your peril, 'k? This code has no functionality for deleting a queue when the setup is shut down.
	__my_queue = __my_queue(__connection)
	__my_queue.declare()
	#print "Q:"
	#print __my_queue
	#__consumer = __connection.Consumer(queues=__my_queue) #we're not using consumer 'cause we're using queue get
	
	#__recv_loop =  drain_consumer(__consumer, timeout=1)
	
	
def shutdown():
	__connection.release()


def send(message,metadata,destination,type_override=None):
	#send a message to one other node.
	__producer.publish(message,routing_key=str(destination)+'-q',headers={"type": type_override if type_override is not None else __my_type,"sender":__username,"meta":metadata}, serializer='json')

	#in the real world, there would probably be a try(), and in the event of an error, a revive() and a reattempt.
	#also in the real world, the sender would be a property of the messages' transit. Here, using this networking framework, we have to add it manually.
	#for those testing adversarial nodes: assume they are unable to forge this 'sender' attribute.
	
	#MODULAR - replace this code with whatever network functionality.
	return

def sendAll(message,metadata,type_override=None):
	#send a message to everybody.
	__producer.publish(message, exchange=__global_exchange, headers={"type":type_override if type_override is not None else __my_type,"sender":__username,"meta":metadata}, serializer='json')
	#IMPORTANT: for reliable broadcast, "send to all" means yourself too.
	#MODULAR - replace this code with whatever network functionality.
	return

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
