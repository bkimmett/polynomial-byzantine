#include <iostream>
#include <ios>
#include <sstream>
#include <string>
#include <cmath>
#include <cfenv>
#include <random>
#include <chrono>
#include <array>
#include <vector>

long num_runs, i;
int num_nodes, j, flip;
bool adv_picks_last;
bool debug = false;

#ifdef DEBUG
	debug = true;
#endif	


bool coinboard_sort( std::array<int,4> in1, std::array<int,4> in2 ){
	if(in1[2] != in2[2]){
		return in1[2] > in2[2]; //adversarial nodes go before nonadversarial
	}
	return in1[0] > in2[0]; //nodes with a positive value, which the adversary mislikes and wants to take over, go before nodes with a neutral or negative value
}

int main( int argc, char* args[] ) {

	//get parameters	
	
	if(argc < 2){
		std::cout << "Usage: " << args[0] << " num_nodes [adv_picks_last] [num_runs]" << std::endl;
		return 1;
	}
	
	num_nodes = std::stoi(args[1]);
	
	if(argc < 3){
		adv_picks_last = true;
	} else {
		std::istringstream(args[2]) >> std::boolalpha >> adv_picks_last;
	}
	
	
	if(argc < 4){
		num_runs = 1000000;
		/*if(debug){
			num_runs = 1;
		}*/
				
	} else {
		num_runs = std::stol(args[3]);
	}

	//setup generated parameters and RNG
	std::cout << "Setting up RNG..." << std::endl;
	
	using engine = std::mt19937_64;
	engine rng;
    std::random_device dev;
    std::seed_seq::result_type rand[engine::state_size]{};  // Use complete bit space

    std::generate_n(rand, engine::state_size, std::ref(dev));
    std::seed_seq seed(rand, rand + engine::state_size);
        
    rng.seed(seed);
	
	// auto seed = chrono::high_resolution_clock::now().time_since_epoch().count();
	// 	std::cout << "Seed = " << seed << std::endl;
	// 	std::mt19937_64 rng(seed);
	
	std::uniform_int_distribution<int> coin(0,1);


	//std::cout << "Setting up constants..." << std::endl;

	const int fault_bound = (num_nodes - 1) / 3; //c++ auto-uses integer div
	std::fesetround(FE_DOWNWARD); //turns 'lrint()' into 'floor()'
	
	const int max_coin_influence_per_column = lrint(5 * sqrt( (double)num_nodes * log(num_nodes) ));

	//std::cout << "Setting up constants..." << std::endl;

	const int odd_or_even = num_nodes % 2; //because nodes are sequences of +1, -1, +1... if there is an odd number of flips the sum can only be an odd number, and if there are an even number of flips the sum can only be an even number. This is to make sure that is upheld.
	
	long result_failed = 0;
	long result_noneed = 0;
	long result_success = 0;
	long result_adv_screwup = 0;
	long runs_with_deletions = 0;
	
	
	long num_runs_percentile = num_runs / 100;
	
	bool deletions_this_run;
	
	//int coinboard[num_nodes][4]; 
	
	std::vector<std::array<int,4>> coinboard (num_nodes);
	
	//now do the thing
	
	for(i = 0; i < num_runs; i++){
		if(num_runs >= 100){
			if(i % num_runs_percentile == 0){
				std::cout << i / num_runs_percentile << "% done." << std::endl;
			}
		} else {
			std::cout << "Run " << i+1 << "/" << num_runs << "." << std::endl;
		}

		deletions_this_run = false;
		
		//phase 1: set up coinboard to the point where the adversary will intervene
		
		for (j = 0; j < num_nodes; j++){
			//reset the coinboard value
			coinboard[j][0] = 0;
			coinboard[j][1] = 0;
			//coinboard[j][2] = (!adv_picks_last && j < fault_bound ? 1 : 0); //1 if this is the first t nodes and the adversary has to pick in advance. Otherwise, all nodes set to 0. 
			
			if (!adv_picks_last && j < fault_bound){
				coinboard[j][2] = 1; 
				continue; //adversary will supply details for its nodes later
			} else {
				coinboard[j][2] = 0;
			}
			
			coinboard[j][3] = 0; //held value is not used for adversarial nodes 
			
			while(coinboard[j][1] < num_nodes){
				flip = coin(rng);
				if(flip == 0){ //tails - adversary's favored direction
					coinboard[j][0]--;
					coinboard[j][1]++;
				} else { //heads - adv uses scheduling to hold flip
					coinboard[j][3] = 1;
					break;
				}

			}
			
		}
		
		//sort coinboard by value so far
		
		std::sort(coinboard.begin(), coinboard.end(), coinboard_sort);
		
		if(debug){
			std::cout << "Sorted coinboard:" << std::endl;
		
			for (j = 0; j < num_nodes; j++){
				std::cout << coinboard[j][0] << " " << coinboard[j][1] << " " << coinboard[j][2] << " " << coinboard[j][3] << std::endl;
			}
		}
		
		//phase 2: adversary takes control of nodes, if they aren't controlled already
		
		if(adv_picks_last){
			for (j = 0; j < fault_bound; j++){
				coinboard[j][2] = 1; //now controlled by adversary
				//coinboard[j][3] = 0; //clear held flip if any //we don't need to do this as adv nodes don't draw from this
			}
		}
		
		//phase 3: adversary runs winningest coins to completion. also get sum of nodes in here
		
		int coinboard_sum = 0;
		
		for (j = 0; j < fault_bound * 2; j++){
			if(abs(coinboard[j][0]) <= max_coin_influence_per_column){
				coinboard_sum += coinboard[j][0];
			} else {
				coinboard[j][0] = 0; //delete column value
				if(!deletions_this_run){
					deletions_this_run = true;
					runs_with_deletions++;
				}
			}
		}
		
		for (j = fault_bound * 2; j < num_nodes; j++){
			//if a held flip exists, release it
			if(coinboard[j][3] != 0){
				coinboard[j][0] += coinboard[j][3];
				coinboard[j][1]++;
			}
			//finish the column
			while(coinboard[j][1] < num_nodes){
				flip = coin(rng);
				if(flip == 0){ //tails
					coinboard[j][0]--;
				} else { //heads
					coinboard[j][0]++;
				}
				coinboard[j][1]++;
			}
			//if the column went over, reset it
			if(abs(coinboard[j][0]) > max_coin_influence_per_column){
				coinboard[j][0] = 0; //clear column's influence - it went over
				if(!deletions_this_run){
					deletions_this_run = true;
					runs_with_deletions++;
				}
			} else {
				coinboard_sum += coinboard[j][0];
			}
		}
		
		if(debug){
			std::cout << "Good-nodes-run coinboard:" << std::endl;
		
			for (j = 0; j < num_nodes; j++){
				std::cout << coinboard[j][0] << " " << coinboard[j][1] << " " << coinboard[j][2] << " " << coinboard[j][3] << std::endl;
			}
		}
		
		//phase 4; figure out how much push the adversary needs to 
		
		int target, max_push;
		
		int coinboard_final_sum = 0;
		
		
		if(coinboard_sum < 0){
			//the adversary doesn't need to push at all!
			//target = 0 - odd_or_even;
			//result_noneed++;
			
			for (j = 0; j < fault_bound; j++){
			
				while(abs(coinboard[j][0]) > max_coin_influence_per_column && coinboard[j][1] < num_nodes){
					//if we're over the influence boundary bring it back towards 0.
					if(coinboard[j][0] < 0){
						coinboard[j][0]++;
					} else {
						coinboard[j][0]--;
					}
					coinboard[j][1]++;
				}
			
				if((num_nodes - coinboard[j][1]) % 2 != 0){
					//if there's an even number of flips left we do a balanced flip - that is, we can just skip straight to adding the sum. if not (this case), we have to add a -1 to it. Then we have to check that we didn't break the influence boundary again.
					if(abs(coinboard[j][0]-1) > max_coin_influence_per_column){
						coinboard[j][0]++;
					} else {
						coinboard[j][0]--;
					}
				}
				coinboard_final_sum += coinboard[j][0];
			}
				
			
		} else {
			target = max_coin_influence_per_column * -1;
			if(target % 2 != odd_or_even){
				target += 1;
			}
			
			for (j = 0; j < fault_bound; j++){
				max_push = coinboard[j][0] + (coinboard[j][1] - num_nodes);

				//TODO: Figure out if fmax is overloaded to work on integers ALSO make sure the right library is set
			
				coinboard[j][0] = fmax(max_push,target);
			
				/*if(abs(max_push) > max_coin_influence_per_column && coinboard[j][0] == max_push){
					coinboard[j][0] = 0; //clear column's influence - it went over
					if(!deletions_this_run){
						deletions_this_run = true;
						runs_with_deletions++;
					}
				}*/
			
				coinboard_final_sum += coinboard[j][0];
			
			}
		
			
		}
		
			
		
		for (j = fault_bound; j < num_nodes; j++){
			coinboard_final_sum += coinboard[j][0];
		}
			
		if(debug || coinboard_final_sum >= 0){
			std::cout << "Run " << i+1 << ": initial sum " << coinboard_sum << ", final sum " << coinboard_final_sum << "." << std::endl;
		}
	
		if(coinboard_sum < 0){
			if(coinboard_final_sum < 0){
				result_noneed++;
			} else {
				result_adv_screwup++;
			}
		} else {
			if(coinboard_final_sum < 0){
				result_success++;
			} else {
				result_failed++;
			}
		
		}
		
	}
	
	std::cout << num_runs << " runs on " << num_nodes << " nodes, adversary " << (adv_picks_last ? "picks last" : "does not pick last") << ", " << result_noneed << " runs didn't need bias, " << result_success << " runs successful, " << result_failed << " runs failed." << std::endl;

	if(result_adv_screwup > 0){
		std::cout << "Adversary screwed up " << result_adv_screwup << " runs." << std::endl;
	}
	if(runs_with_deletions > 0){
		std::cout << runs_with_deletions << " runs had columns deleted for going over the influence limit." << std::endl;
	}


	return 0;
}
