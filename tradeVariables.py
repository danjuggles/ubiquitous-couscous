
# varaibles used for both backtesting and live strategy
# currency pair
currencyPair = 'EUR_GBP'

# percentage of current balance to use for placing new trades
lotSizePrcnt = 0.1	# 1 = 100%
lotSize = 10000

# take profit and trailing stop loss pip values
tpPips = 200
tlPips = 50

takeProfitMin = 15 # this is in GBP

# The number of ticks to receive before automatically self terminating the algo
# set this to 0 to nullify it and therefore run indefinitely
maxTicks = 0

#~~~~~~~~~~~~~~~~~~~
# Strategy - momentum
movingAverage = 600

#~~~~~~~~~~~~~~~~~~~
# Strategy - dual ema crossover
# these will be times by lots of 5 seconds
# so 50 would be 240 * 5 = 1200 seconds, 1200/60 = 20 mins
emaFast = 200
emaSlow = 1000

emaThreshold = 60

maxOpenTrades = 1

#~~~~~~~~~~~~~~~~~~~
# Backtest only variables
# chose the start and end times for the data request
# there are limits on ow much data can be requested at once
startDate = '02 Feb 2021' # must be in format DD mon YYYY
endDate = '02 Mar 2021' # must be in format DD mon YYYY

# time interval for back testing
timeInterval = 'M30'

# define the array for the ma
MA_intervals = [15, 30, 60, 120]