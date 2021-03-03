# ubiquitous-couscous

## Set up
Create an account with oanda and generate the access token. You'll need to add your account ID and access token in a file called `oandaAccountInfo.py` There is a template file for this

As EMAs need sufficient data to start working, we can grab some recent market data to prime the dataframes. This allows the EMAs to start working as soon as the script is run

Note. This bit is pants. "Today's date" needs to be manually entered in  `tradeVariables.py`, this is a relic of starting the backtesting work

## Strategy
### Indicator
Fast and slow EMAs

### Trade entry
We detect when the EMAs cross, then wait for a divergence threshold. When the threshold is met a trade is created with a `Trailing Stop Loss` 

### Trade exit
1. When the EMAs cross back we look to see if we should close the trade. Trade is closed if it has made sufficient profit
2. Trailing Stop loss is triggered