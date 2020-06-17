# Byzantine Agreement in Expected Polynomial Time (King-Saia)

This code goes with the thesis "Improvement and Partial Simulation of King & Saia’s Expected-Polynomial-Time Byzantine Agreement Algorithm", and contains the implementation and simulation of the titular algorithm, as well as the thesis's improvements. 

For details on the underlying algorithms, please see the thesis (http://hdl.handle.net/1828/11836) or King and Saia's original paper (https://dl.acm.org/doi/10.1145/2837019).


## Using the Simulation

### Requirements

You’ll need the following on your computer:

• Python 2.7 (when I started working on this Python 2 wasn’t deprecated yet. Sorry.)
	To get Python 2.7 on Mac: `brew install https://raw.githubusercontent.com/Homebrew/homebrew-core/86a44a0a552c673a05f11018459c9f5faae3becc/Formula/python@2.rb` - it's been removed from the regular homebrew library.
	
• Kombu networking library for Python [`pip2 install kombu`]
• blist large-list library [`pip2 install blist`] 
• RabbitMQ messaging server (https://www.rabbitmq.com/)

### Quick Start

To get started in a hurry:

1. Put all the .py files (`multibyz_kingsaia_adversary.py`, `multibyz_kingsaia_client_adversary.py`, `multibyz_kingsaia_network_adversary.py`, `multibyz_kingsaia_node_adversary.py`, `multibyz_kingsaia_runner_adversary.py`) in the same folder. (Python files that don't end in `_adversary.py` are from an older revision of the code and can be ignored.)

2. Make a new folder `logs/` inside that folder if one doesn't already exist.

3. In a command prompt, run the messaging server: `rabbitmq-server`. This window needs to stay open for as long as the program is running.

4. In another command prompt (in the folder where the files are), run the runner, which starts and stops (most of) the other parts of the program: `python multibyz_kingsaia_runner_adversary.py <num_nodes>`. The slot where `<num_nodes>` is should have an integer in it: the number of total nodes to run. The runner will start all nodes, as well as the client, and drop you in the client.

5. The runner will create a file, `multibyz_kingsaia_nodenames`, with the names of the running nodes.

6. In a third command prompt, run the adversary: `python ./multibyz_kingsaia_adversary.py multibyz_kingsaia_nodenames > logs/log_adversary.txt`. 

7. You can now send commands to the system from the command prompt that has the client (see below for a list of commands). To stop the system, type `halt` in the command prompt, or use Ctrl-C. The client will ensure everything properly shuts down, including the adversary.

8. Logs are stored in the `logs/` folder. Each node logs to a text file automatically. The adversary command shown above redirects its output (normally to stdout) into a text file, instead.

9. To stop the messaging server, use Ctrl-C in its window.

### Client Commands

The client is multithreaded, and will check for messages in the background, printing them to stdout. *Most* commands will be processed in the background.

#### Basic Messaging

• `msg <dest> <message>` - Used to send a message (a string) to a node. This was mostly used for initial testing of networking. The message will be printed when it's received. `<dest>` should be a node name and cannot contain spaces. Anything after that will be treated as part of the message.
• `msgall <message>` - Used to send a message to every node. Basically `msg`, but sent to all active nodes. The message will be printed when it's received.
• `rb <dest> <message>` - Used to tell a node (`<dest>`) to start reliable broadcast, with message content `<message>`. Like `msg`, `<dest>` must be a node name and can't contain spaces. Nodes that accept the reliably broadcast message will print it. Mostly used for testing reliable broadcast.

#### Running Byzantine Agreement Instances

• `byz <num_nodes_true> [<num_nodes_false>]` - **Used to start a byzantine agreement instance.** You'll be using this command a lot. `<num_nodes_true>` indicates the number of nodes that start with the initial value 'True'. `<num_nodes_false>`, if present, indicates the number of nodes that start with the initial value 'False'. 
If only `<num_nodes_true>` is present in the command, all nodes unaccounted for will start with 'False'. If both  `<num_nodes_true>` and `<num_nodes_false>` are present, all nodes unaccounted for will start with a randomly chosen value (so you can do `byz 0 0` to make all nodes' initial values be chosen at random).
When nodes make a decision on the result of a byzantine agreement instance, the client will show their decisions.
• `multibyz <num_nodes_true> <num_nodes_false> <num_runs> <delay>` - Used to start many byzantine agreement instances over a span of time. The first part of the command is like `byz`, except `<num_runs>` iterations will be started, with a delay of `<delay>` seconds after each run to prevent the machine from becoming overloaded. For most behaviors, a delay of 150 seconds (2.5 minutes) should give enough time for the previous instance to complete. 
Note that this command **does not return to the command prompt** until all the instances are done, so please use it responsibly!

#### Adversary Control

• `adv <bracha_behavior> [<coin_behavior>]` - Used to set the adversary's behaviors, which will be applied to future byzantine agreement instances. `<bracha_behavior>` indicates what behavior to apply to Modified-Bracha, and `<coin_behavior>` what behavior to apply to Global-Coin. See below for a list of behaviors and what they do. Entering "none" for one of the behaviors will clear it.
• `adv_get` - Gets the adversary's current behaviors it is set to use. The adversary will respond in a message to the client.
• `adv_release <byzantine_instance_ID> <epoch> <iteration> [<wave>]` - If the adversary is not set to defer when it realizes it's in an unwinnable situation, it may end up holding Modified-Bracha messages indefinitely. To release those held messages, use this command. If `<wave>` is omitted, messages held for all three waves of Modified-Bracha will be released at once.
(There's no command to release held Global-Coin messages at this time. My apologies.)

#### Misc

• `halt` - Shuts down all nodes and adversary. You'll need to stop the messaging server manually.


### Adversary Behaviors

You can tell the adversary to use these behaviors with the `adv` command. 

#### Bracha Behaviors

• `none` - Do nothing.
• `split_vote` - Force all nodes to run Global-Coin, and accept its result.
• `split_hold` - Force all nodes to run Global-Coin, but ignore its result. Nodes will instead hold their current value, which *should* be the adversary's chosen value.
• `force_decide` - Force all nodes to decide on the adversary's chosen value.
• `split_mux` - A mix of `split_vote` and `split_hold`. Used for the 'Deadlock' attack described in the thesis.
• `lie_like_a_rug` - Corrupted nodes insist their value is the adversary's chosen value, whether or not they're taken seriously.

#### Global-Coin behaviors

• `none` - Do nothing.
• `bias` - Bias the shared coin flip in the adversary's chosen direction.
• `bias_reverse` - Bias the shared coin flip in the direction opposite the adversary's chosen direction. Used for the 'Deadlock' attack.
• `split` - Split the shared coin flip, so different nodes will see different results. **Not tested, may not work.** Use at own risk.

## Changing Basic Parameters (Logging, Adversary Chosen Value, Adversary Message Holding)

Certain parameters you may want to change are stored in the first few lines of the python scripts of the implementation.

**In `multibyz_kingsaia_node_adversary.py`:**

• `debug_rb` (default `False`) - Prints out all reliable broadcast internal messages this node receives if set to `True`. This will generate a LOT of output and is best left off unless you're trying to debug reliable broadcast.
• `debug_rb_coin` (default `False`) - Similar to `debug_rb`, but prints out reliable broadcast messages related to Global-Coin coin flip messages. EVEN MORE output than `debug_rb`, best left off.
• `debug_rb_accept` (default `True`) - Prints out all reliable broadcast messages a node accepts. Technically prints twice - once before a message is filtered by the adversary, and once after it comes back. This is the easy way to keep tabs on all messages a node receives.
• `debug_byz` (default `True`) - Prints out various logging messages relating to the state of the byzantine agreement instance in general, and Modified-Bracha in particular. Probably best kept on.
• `debug_show_coinboards` (default `True`) - Once a node's view of the blackboard is complete, the node will print it.


**In `multibyz_kingsaia_adversary.py`:**

• `defer_in_unwinnable_situations` (default `True`) - For ease of automated use, the adversary can detect iterations when all good nodes start unanimous, and automatically release held Modified-Bracha messages in these circumstances (as the adversary wouldn't be able to influence the iteration anyway - see **CITE Bracha 1987a**). This auto-release will happen if this variable is set to `True`, and not if it is False.
• `default_target` (default `False`) - This is the adversary's chosen value. If you want the adversary to try and push `True`, set this to `True` instead.
• `known_bracha_gameplans` and `known_coin_gameplans` - These are the behaviors the adversary knows about. If you want to add a new behavior (see below), add its name to this list so that the adversary knows it's a valid one.
• `debug` (default `True`) - Turns on logging of most basic adversary actions. Turning this off may not silence all output, because I didn't pipe every log message through the logging function. Oops.
• `debug_coin_acks` (default `False`) - Turns on logging of Global-Coin acknowledgements. This will generate a LOT of output and unless you're specifically debugging the inner workings of Global-Coin, you probably want to leave it off.
• `debug_messages` (default `False`) - Turns on logging of all messages the adversary receives from any source. Mostly used for debugging message receiving. Another one you can safely leave off.


## Customizing the Simulation



### Program Structure


### Networking Between Processes And How to Make it Distributed

As I have it, the code is set up for simulation on a single machine - the messaging server, nodes, adversary, and all other parts of the program are set up to run on the same computer.

If you want to make it distributed, you'll need to replace the functions in `multibyz_kingsaia_network_adversary.py` with your own implementations.

The functions in that file are as follows:

• `init()` - Used by nodes, the client, and the runner script to set up their connections.
• `init_adversary()` - Used to set up the adversary's connection.
• `shutdown()` - Used to close connections for all parties.
• `send()` - Used to send messages to one other party.
• `sendAsAdversary()` - Used by the adversary to release a message a node was going to accept after it was going to hold it.


### Implementing Process-Epoch


### Adding New Adversary Behaviors



