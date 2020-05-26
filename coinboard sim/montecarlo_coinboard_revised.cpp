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
int adv_chosen_direction;
bool adv_picks_last;

#ifdef DEBUG
	const bool debug = true;
#else
	const bool debug = false;
#endif	


bool coinboard_sort_posfirst( const std::array<int,6> &in1, const std::array<int,6> &in2 ){
	if(in1[2] != in2[2]){
		return in1[2] > in2[2]; //adversarial nodes go before nonadversarial
	}
	return in1[0] > in2[0]; //nodes with a positive value, which the adversary mislikes and wants to take over, go before nodes with a neutral or negative value
}

bool coinboard_sort_negfirst( const std::array<int,6> &in1, const std::array<int,6> &in2 ){
	if(in1[2] != in2[2]){
		return in1[2] > in2[2]; //adversarial nodes go before nonadversarial
	}
	return in1[0] < in2[0]; //nodes with a negative value, which the adversary mislikes and wants to take over, go before nodes with a neutral or positive value
}

void print_coinboard(std::vector<std::array<int,6>> coinboard){
	for (j = 0; j < num_nodes; j++){
		std::cout << coinboard[j][0] << ":" << coinboard[j][1] << " " << (coinboard[j][2] ? "adv" : "OK") << " (" << coinboard[j][3] << ")" << std::endl;
	}
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
		
		#ifdef DEBUG
			num_runs = 1;
		#else
			num_runs = 1000000;
		#endif
				
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
	
	// lesser RNG setup (not as good as above. don't use this)
	// auto seed = chrono::high_resolution_clock::now().time_since_epoch().count();
	// 	std::cout << "Seed = " << seed << std::endl;
	// 	std::mt19937_64 rng(seed);
	
	std::uniform_int_distribution<int> coin(0,1);


	//std::cout << "Setting up constants..." << std::endl;

	const int fault_bound = (num_nodes - 1) / 3; //c++ auto-uses integer div
	std::fesetround(FE_DOWNWARD); //turns 'lrint()' into 'floor()'
	
	const int max_coin_influence_per_column = lrint(5 * sqrt( (double)num_nodes * log(num_nodes) ));
	
	std::cout << "Max coin influence per column = " << max_coin_influence_per_column << std::endl;

	//std::cout << "Setting up constants..." << std::endl;

	const int odd_or_even = num_nodes % 2; //because nodes are sequences of +1, -1, +1... if there is an odd number of flips the sum can only be an odd number, and if there are an even number of flips the sum can only be an even number. This is to make sure that is upheld.
	
	long result_failed = 0;
	long result_noneed = 0;
	long result_success = 0;
	long result_adv_screwup = 0;
	long runs_with_deletions = 0;
	long runs_adv_bias_lastminute = 0;
	
	
	long num_runs_percentile = num_runs / 100;
	
	bool deletions_this_run, adv_deletions_this_run;
	bool adv_tried_faircoin;
	
	//int coinboard[num_nodes][4]; 
	
	//coinboard column structure is as follows:
	//[0] = sum of column
	//[1] = number of flips
	//[2] = adversarial? 0/1 (T/F)
	//[3] = held value
	//[4] = sum of column backup (for adversary)
	//[5] = number of flips backup (for adversary)
	// we don't need to backup held value because if adversary has to restore to backup after generating fair coin flip, the held value will not be used.
	
	std::vector<std::array<int,6>> coinboard (num_nodes);
	
	//now do the thing
	
	for(i = 0; i < num_runs; i++){
		//set up adversary direction
		//adv_chosen_direction = 1; //adversary loves heads
		//adv_chosen_direction = -1; //default: adversary loves tails
		adv_chosen_direction = coin(rng) ? 1 : -1;
		//you could also set this to "adv_chosen_direction = coin(rng) ? 1 : -1;" to get randomly swapping chosen directions
		#ifdef DEBUG
			std::cout << "Adversary's chosen direction is " << adv_chosen_direction << "." << std::endl;
		#endif
		
	
		if(num_runs >= 100){
			if(i % num_runs_percentile == 0){
				std::cout << i / num_runs_percentile << "% done." << std::endl;
			}
		} else {
			std::cout << "Run " << i+1 << "/" << num_runs << "." << std::endl;
		}

		deletions_this_run = false;
		adv_tried_faircoin = false;
		
		//phase 1: set up coinboard to the point where the adversary will intervene
		
		for (j = 0; j < num_nodes; j++){
			//reset the coinboard value
			coinboard[j][0] = 0;
			coinboard[j][1] = 0;
			//coinboard[j][2] = (!adv_picks_last && j < fault_bound ? 1 : 0); //1 if this is the first t nodes and the adversary has to pick in advance. Otherwise, all nodes set to 0. 
			
			coinboard[j][3] = 0; //held value is not used for adversarial nodes, and it's cleared for everyone else
			
			if (!adv_picks_last && j < fault_bound){
				coinboard[j][2] = 1; 
				coinboard[j][4] = 0;
				coinboard[j][5] = 0;
				continue; //adversary will supply details for its nodes later
			} else {
				coinboard[j][2] = 0;
			}
			
			coinboard[j][3] = 0; //held value is not used for adversarial nodes 
			
			while(coinboard[j][1] < num_nodes){
				flip = coin(rng) ? 1 : -1;
				if(flip == adv_chosen_direction){ //adversary's favored direction
					//coinboard[j][0]--;
					coinboard[j][0] += flip;
					coinboard[j][1]++;
				} else { //the other way - adv uses scheduling to hold flip
					coinboard[j][3] = flip;
					break;
				}

			}
			
		}
		
		//sort coinboard by value so far
		if(adv_chosen_direction == 1){
			std::sort(coinboard.begin(), coinboard.end(), coinboard_sort_negfirst);
		} else {
			std::sort(coinboard.begin(), coinboard.end(), coinboard_sort_posfirst);
		}
		
		#ifdef DEBUG 
			//print coinboard
			std::cout << "Sorted coinboard:" << std::endl;
		
			print_coinboard(coinboard);
		#endif
		
		//phase 2: adversary takes control of nodes, if they aren't controlled already
		
		if(adv_picks_last){
			//if adv picks first, stopped nodes will be in the MIDDLE, adv nodes will be at the START
			//if adv picks last, stopped nodes will be at the START, adv nodes will be in the MIDDLE
			for (j = fault_bound; j < fault_bound * 2; j++){
				coinboard[j][2] = 1; //now controlled by adversary
				coinboard[j][4] = coinboard[j][0]; //backup coinboard results, just in case 
				coinboard[j][5] = coinboard[j][1]; 
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
				//if(!deletions_this_run){
				deletions_this_run = true;
				//	runs_with_deletions++;
				//}
			}
		}
		
		for (j = fault_bound * 2; j < num_nodes; j++){
			//either way, though, working nodes will always be at the END
			if(coinboard[j][3] != 0){
				//if a held flip exists, release it
				coinboard[j][0] += coinboard[j][3];
				coinboard[j][1]++;
			#ifdef DEBUG
				coinboard[j][3] = 0;
			#endif
			}
			//finish the column
			while(coinboard[j][1] < num_nodes){
				flip = coin(rng) ? 1 : -1;
				coinboard[j][0] += flip;
				/*if(flip == 0){ //tails
					coinboard[j][0]--;
				} else { //heads
					coinboard[j][0]++;
				}*/
				coinboard[j][1]++;
			}
			//if the column went over, reset it
			if(abs(coinboard[j][0]) > max_coin_influence_per_column){
				coinboard[j][0] = 0; //clear column's influence - it went over
				//if(!deletions_this_run){
				deletions_this_run = true;
					//runs_with_deletions++;
				//}
			} else {
				coinboard_sum += coinboard[j][0];
			}
		}
		
		#ifdef DEBUG
			std::cout << "Good-nodes-run coinboard:" << std::endl;
		
			print_coinboard(coinboard);
		#endif
		
		//phase 4; figure out how much push the adversary needs to 
		
		int target, max_push;
		
		int coinboard_final_sum = 0;
		int coinboard_original_sum = coinboard_sum;
		
		int adv_nodes_begin = adv_picks_last ? fault_bound : 0;
		int adv_nodes_end = adv_picks_last ? fault_bound * 2 : fault_bound;
		
		
		adv_deletions_this_run = false;
		
		if(coinboard_sum * adv_chosen_direction > 0){
			//the adversary doesn't need to push at all! Assuming the fair coin flip doesn't go too far away from the current situation.
			adv_tried_faircoin = true;
			
			for (j = adv_nodes_begin; j < adv_nodes_end; j++){

				if(coinboard[j][3] != 0){
					//if a held flip exists, release it
					coinboard[j][0] += coinboard[j][3];
					coinboard[j][1]++;
					#ifdef DEBUG
						coinboard[j][3] = 0;
					#endif
				}
				//finish the column
				while(coinboard[j][1] < num_nodes){
					flip = coin(rng) ? 1 : -1;
					coinboard[j][0] += flip;
					/*if(flip == 0){ //tails
						coinboard[j][0]--;
					} else { //heads
						coinboard[j][0]++;
					}*/
					coinboard[j][1]++;
				}
				//if the column went over, reset it
				if(abs(coinboard[j][0]) > max_coin_influence_per_column){
					coinboard[j][0] = 0; //clear column's influence - it went over
					adv_deletions_this_run = true;
				}
				coinboard_sum += (coinboard[j][0] - coinboard[j][4]); //store new value for this column and unwind previous value
			
			}
					
		} 
		
		#ifdef DEBUG
			std::cout << "Intermediate coinboard:" << std::endl;

			print_coinboard(coinboard);
		#endif
		
		if (coinboard_sum * adv_chosen_direction <= 0) { 
			//the adversary does need to push
			if(adv_tried_faircoin){ //keep track of runs we had to bias because of bad fair coin rng
				runs_adv_bias_lastminute++;
				#ifdef DEBUG
				std::cout << "Adversary fair coin attempt failed." << std::endl;
				#endif
			}
			if(adv_deletions_this_run){
				//when the adv emits biased flips it takes care not to get its columns deleted - the deletions we saw earlier never happened because we rewind and write over them
				adv_deletions_this_run = false;
			}
		
			target = max_coin_influence_per_column * adv_chosen_direction;
			if(abs(target % 2) != odd_or_even){
				target -= adv_chosen_direction;
			}
			
			for (j = adv_nodes_begin; j < adv_nodes_end; j++){
				if(adv_tried_faircoin){
					//if we need to rewind previous fair coin flips, do that first
					coinboard[j][0] = coinboard[j][4];
					coinboard[j][1] = coinboard[j][5];
				}

				if(adv_chosen_direction == 1){
					max_push = coinboard[j][0] + (num_nodes - coinboard[j][1]); //amount of push is in positive direction
					coinboard[j][0] = fmin(max_push,target);
				} else {
					max_push = coinboard[j][0] + (coinboard[j][1] - num_nodes); //amount of push is in negative direction
					coinboard[j][0] = fmax(max_push,target);
				}
				
			}
				
		}
		
		#ifdef DEBUG
			std::cout << "Final coinboard:" << std::endl;

			print_coinboard(coinboard);
		#endif
		
	
		if(deletions_this_run || adv_deletions_this_run){ //if fair coin flips got a column deleted, then, well, here we are
			runs_with_deletions++;
		}
			
		for (j = 0; j < num_nodes; j++){ // calculate final sum
			coinboard_final_sum += coinboard[j][0];
		}
			
		if(debug || coinboard_final_sum * adv_chosen_direction <= 0){
			std::cout << "Run " << i+1 << ": initial sum " << coinboard_original_sum << ", intermediate sum " << coinboard_sum << ", final sum " << coinboard_final_sum << "." << std::endl;
		}
	
		if(coinboard_original_sum * adv_chosen_direction > 0){ //track results
			if(coinboard_final_sum * adv_chosen_direction > 0){
				if(adv_tried_faircoin && coinboard_sum * adv_chosen_direction <= 0){
					result_success++;
				} else {
					result_noneed++;
				}
			} else {
				result_adv_screwup++;
			}
		} else {
			if(coinboard_final_sum * adv_chosen_direction > 0){
				result_success++;
			} else {
				result_failed++;
			}
			
		}
		
	}
	
	std::cout << num_runs << " runs on " << num_nodes << " nodes, adversary " << (adv_picks_last ? "picks last" : "does not pick last") << ", " << result_noneed << " runs didn't need bias, " << result_success << " runs successful (" << runs_adv_bias_lastminute << " at the last minute), " << result_failed << " runs failed." << std::endl;

	if(result_adv_screwup > 0){
		std::cout << "Adversary screwed up " << result_adv_screwup << " runs." << std::endl;
	}
	if(runs_with_deletions > 0){
		std::cout << runs_with_deletions << " runs had columns deleted for going over the influence limit." << std::endl;
	}

	return 0;
}
