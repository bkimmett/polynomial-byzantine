# Coinboard Sim

This application lets you simulate Global-Coin's blackboard, with the adversary running the 'biased coin' behavior.

### Compilation

`g++ -O3 montecarlo_coinboard_revised.cpp -std=c++11 -o montecarlo_coinboard_revised`

You can compile with `-DDEBUG` to enable a lot of debug output about the state of the blackboard during a simulation.

Don't use `montecarlo_coinboard_real.cpp`. It's old.

### Running

`./montecarlo_coinboard_revised <num_nodes> [<adv_picks_last>] [<num_runs>]`

`<num_nodes>` is the number of nodes (_n_) in the process. The adversary can control up to _t < n/3_ nodes.
`<adv_picks_last>` should be either `true` or `false`. If `true`, the adversary picks which nodes to corrupt in the middle of the process. If `false`, the simulation acts as if the adversary had already corrupted nodes before the iteration of Global-Coin began.
  If you don't specify a value for `<adv_picks_last>`, the simulation will assume `true`.
`<num_runs>` is the number of times to run the simulation. If you don't specify a number, the simulation will assume 1,000,000 (1 million) runs as a default. If you compiled with `-DDEBUG` and don't specify a number, the simulation will assume 1 (one) run, instead.

Once the run is over, you'll see a readout like this:

`1000000 runs on 1778 nodes, adversary does not pick last, 575307 runs didn't need bias, 424693 runs successful (141731 at the last minute), 0 runs failed.`

"Successful" is from the adversary's perspective - a run is 'successful' if the adversary biased the blackboard.
"At the last minute" means that a run was already veering in the adversary's chosen direction, but if the adversary had had its corrupted nodes emit fair coin flips, probability would have made the adversary lose the run - forcing it to emit biased coin flips. Note that in a more realistic (less simulated) setting, 'last minute' runs's biased coin flips would not need to yield a sum very far in the adversary's chosen direction, making them hard to detect.

If you see a line saying the adversary "screwed up" some number of runs, this means that a run was previously in the adversary's chosen direction and they ended up pushing it away from their chosen direction. This almost always indicates some sort of bug in the code, and hopefully shouldn't happen.
