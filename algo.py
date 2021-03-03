# import libraries
import json

import oandapyV20
from oandapyV20 import API
from oandapyV20.contrib.requests import MarketOrderRequest, TakeProfitOrderRequest, StopLossOrderRequest, TrailingStopLossOrderRequest, TrailingStopLossDetails
from oandapyV20.exceptions import V20Error, StreamTerminated

import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.accounts as accounts
#from oandapyV20.endpoints.pricing import PricingStream
import oandapyV20.endpoints.pricing as pricing
from itertools import count
#import matplotlib
#matplotlib.use('TKAgg')
#from matplotlib.animation import FuncAnimation
#import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import datetime
from datetime import datetime
from dateutil import parser
import seaborn as sns; sns.set()
import random
import math

import oandaTradeInstructions as ti
#from tabulate import tabulate

from oandaAccountInfo import account_id, access_token
from tradeVariables import currencyPair, timeInterval, startDate, endDate, MA_intervals, maxTicks, emaThreshold, emaFast, emaSlow, lotSize, movingAverage, maxOpenTrades, tlPips, takeProfitMin

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 20)

#matplotlib.interactive(True)

client = oandapyV20.API(access_token=access_token)

pricingParams={"instruments":currencyPair}

r = trades.TradesList(account_id)
p = pricing.PricingStream(accountID=account_id, params=pricingParams)

# show the endpoint(s) as constructed for this call
print("Oanda api")
print("Trade info request:{}".format(r))
print("Pricing Stream:{}".format(p),"\n")

# send the requests
rv = client.request(r)
ps = client.request(p)

# print the response on trades in json format
print("Response - Trades:\n{}".format(json.dumps(rv, indent=2)))

if rv['trades'] == []:
	tradeID = None
	print(tradeID)
else:
	tradeID = int(rv['trades'][0]['id'])
	print(tradeID)


# grab recent market data rather to initialiase the emas
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#set up the parameters needed
params={#"from": datetime.strptime(startDate, '%d %b %Y').isoformat('T'), # sends the date in RFC3339 format
        #"to": datetime.strptime(endDate, '%d %b %Y').isoformat('T'), # sends the date in RFC3339 format
        "granularity":timeInterval,
        "price":'A'}

# construct the request for the api
e = instruments.InstrumentsCandles(instrument=currencyPair,params=params)
data = client.request(e)

#print(data)
# construct the response results
results= [{"time":x['time'],"closeoutAsk":float(x['ask']['c'])} for x in data['candles']]

# costruct the dataframe to hold the results
df = pd.DataFrame(results)#.set_index('time')

df.index = pd.DatetimeIndex(df["time"])

# transforms the time information to a DatetimeIndex object
#self.df.index = pd.DatetimeIndex(self.df["time"])

# Convert items back to numeric, as this is more data in string form from oanda
df['closeoutAsk'] = pd.to_numeric(df["closeoutAsk"],errors='ignore')

print(df.tail)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


#plt.style.use('fivethirtyeight')
#
#x_values = []
#y_values = []
#y2_values = []
#y3_values = []


class mainLoop():
	ticksRxd = 0
	openTrades = 0

	ordersPlaced = 0
	tradesPlaced = 0
	tradeID = 0
	price = 0

	def __init__(self, lotSize, movingAverage, emaFast, emaSlow, df):
		# key info variables to get from oanda
		self.openTrades = 0
		self.currentBalance = 0
		self.pl = 0
		self.usedMargin = 0
		self.unrealizedPL = 0

		self.crossovers = 0

		# inititialise a data frame
		self.df = df
		self.dfr = pd.DataFrame()

		print("dfr shape: ",self.dfr.shape)

		# stuff used in strategy - momentum
		self.movingAverage = movingAverage

		# stuff used in strategy - ema crossover
		self.emaFast = emaFast
		self.emaSlow = emaSlow
		self.changeState = False
		self.diffSignPrevious = None

		# details used in opening/placing trades
		self.lotSize = lotSize
		self.goLong = False
		self.data = {} # initialise an empty dictonary for placing trades
		self.trailingStopLossOnFill = {} # initialise an empty dictonary for placing the trailing loss part of a trade
		self.tlPips = tlPips

		# grab the account info from oanda
		self.getDeets()

		# start the getTicks function going to get live market data from oanda
		self.getTicks()

	# a class method that gets the raw tick data from oanda
	def getTicks(self):
		for tickData in ps:
			if not (tickData["type"]=="HEARTBEAT"):	# for analysing the market we don't want the heartbeat messages getting in the way
				self.ticksRxd += 1

				# get the latest account details
				self.getDeets()

				# get info on any open trades
				self.getTrades()

				# print out an updated counter
				print("Ticks Received: ",self.ticksRxd)
				#print(tickData,"\n")

				# this function updates the dataframe with the new info
				self.updateDataFrame(tickData)

			# a way to auto terminate if required
			if (maxTicks != 0 and self.ticksRxd == maxTicks):
				p.terminate("All ur ticks r belong to us")

	# look for:
	# balance, margin outlay, number of trades,
	def getDeets(self):
		# set up the request to oanda
		request = accounts.AccountDetails(account_id)
		# send the resonse and look at the output
		response = client.request(request)
		
		# parse the response to get the info we want, in a format we want it in
		self.openTrades = int(response['account']['openTradeCount'])
		self.currentBalance = float(response['account']['balance'])
		self.pl = float(response['account']['positions'][0]['pl'])
		self.usedMargin = float(response['account']['marginUsed'])

		#print("Account info")
		#print('Current balance: ',self.currentBalance,'GBP')
		#print('Total profit/loss',self.pl,'GBP')
		
		#print("Trade info")
		print('Number of open trades: ',self.openTrades)
		#print('Used margin: ',self.usedMargin,"GBP")

	def getTrades(self):
		r = trades.TradesList(account_id)
		
		if self.openTrades != 0:
			rv = client.request(r)

			self.tradeID = int(rv['trades'][0]['id'])
			
			self.unrealizedPL = float(rv['trades'][0]['unrealizedPL'])
			print("unrealizedPL:",self.unrealizedPL)

	def openTrade(self, goLong):
		self.goLong = goLong

		# check to see if we want a short or a long trade and set lotSize accordingly
		if (self.goLong == True):
			self.lotSize = self.lotSize
		elif (self.goLong == False):
			self.lotSize = -self.lotSize

		print(self.goLong,self.lotSize)

		# set the trailing loss pip level
		self.tlPips = tlPips/10000 # to scale it for oandas needs

		# sets up the data/dicts for the trailing stop loss element of opening a trade
		self.trailingStopLossOnFill = TrailingStopLossDetails(distance=self.tlPips).data

		# sets up the data/dicts for the full request
		self.data = MarketOrderRequest(instrument=currencyPair, units=self.lotSize, trailingStopLossOnFill=self.trailingStopLossOnFill).data

		# Check to see if we can place more orders first
		if self.openTrades < maxOpenTrades:
			# set up the order
			order = orders.OrderCreate(accountID=account_id, data=self.data)
	
			# place the order
			response = client.request(order)

			# increment the counters
			self.tradesPlaced += 1
			self.ordersPlaced += 1

			# do some printing
			print("Trades placed this session ",self.tradesPlaced)
			print("Orders placed this session ",self.ordersPlaced)
			print(response)

			# look at the response and parse out the info we need, and convert it to something useful
			self.tradeID = int(response["orderFillTransaction"]["tradeOpened"]["tradeID"])
			self.price = float(response["orderFillTransaction"]["tradeOpened"]["price"])

			print("tradeID: ",self.tradeID,"price: ",self.price)

			# call the method to add the take profit point
			#self.setTakeProfit(self.tradeID, self.price, goLong)
			#self.setTrailingStop(self.tradeID, self.price, goLong)

		else:
			print("no room at the inn, max concurrent trades already open")	

	def updateDataFrame(self, tickData):
		# set up a pandas dataframe with the key info we want
		self.df = self.df.append(pd.DataFrame([{'time': tickData['time'],'closeoutAsk':float(tickData['closeoutAsk'])}],index=[tickData["time"]]))

		# transforms the time information to a DatetimeIndex object
		self.df.index = pd.DatetimeIndex(self.df["time"])

        # Convert items back to numeric, as this is more data in string form from oanda
		self.df['closeoutAsk'] = pd.to_numeric(self.df["closeoutAsk"],errors='ignore')

		print("df shape:",self.df.shape)
		#print("----------------df----------------")
		#print(self.df.shape)
		#print(self.df.tail())

		# resamples the data set to a new, homogeneous interval
		self.dfr = self.df.resample('5s').last().bfill()

		self.maGradient(self.dfr)

	def maGradient(self, dfr):
		#print(type(dfr['time'].iloc[-1]), type(dfr['closeoutAsk'].iloc[-1]))
		#dfr['gradient'] = np.sign(dfr['closeoutAsk'].rolling(5).mean())

		#plt.pause(0.01)
		self.dfr['ema fast'] = self.dfr['closeoutAsk'].ewm(span=self.emaFast,min_periods=self.emaFast).mean()
		self.dfr['ema slow'] = self.dfr['closeoutAsk'].ewm(span=self.emaSlow,min_periods=self.emaSlow).mean() #min_periods


		self.dfr['ema diff'] = (self.dfr['ema fast'] - self.dfr['ema slow']) * 1000000 # this scales it to a normal number
		#print(self.dfr['ema diff'].iloc[-1])
		#print("fast:", self.dfr['ema fast'].iloc[-1], "slow:", self.dfr['ema slow'].iloc[-1], "diff:", self.dfr['ema diff'].iloc[-1])
		#print("----------------self.dfr----------------")
		#print(self.dfr.shape)
		#print( "diff:", self.dfr['ema diff'].iloc[-1], "\n\tiloc[-2]", np.sign(self.dfr['ema diff'].iloc[-2]), self.dfr['ema diff'].iloc[-2], "\n\tdiffprev", self.diffSignPrevious, "\n\tiloc[-1]", np.sign(self.dfr['ema diff'].iloc[-1]), self.dfr['ema diff'].iloc[-1])
		print( "diff:", self.dfr['ema diff'].iloc[-1], "self.dfr: shape:", self.dfr.shape, "size:", self.dfr.size)
		#print(self.dfr.tail())

		# detect a cross over event of the  2 emas by comparing the sign of the last 2 lines
		# need to ensure we have enough data in the frame to do this check, so wait for a wfew ticks
					#if self.ticksRxd > 5 and not math.isnan(self.dfr['ema diff'].iloc[-2]):
		# compare the last 2 lines of the frame. Also check to make sure they are both actual numbers
		if np.isnan(self.dfr['ema diff'].iloc[-1]) == False:
			print("number of crossovers:", self.crossovers)
			if ((np.sign(self.dfr['ema diff'].iloc[-1])) != self.diffSignPrevious) and (self.diffSignPrevious != None):
				self.changeState = True
				self.crossovers += 1
				#print("\tCross over detected!", "\n\tiloc[-2]", np.sign(self.dfr['ema diff'].iloc[-2]), self.dfr['ema diff'].iloc[-2], "\n\tdiffprev", self.diffSignPrevious, "\n\tiloc[-1]", np.sign(self.dfr['ema diff'].iloc[-1]), self.dfr['ema diff'].iloc[-1])
				print("\tcrossover detected!", "number of crossovers:", self.crossovers)
				# lets call a method that can do stuff based on this detection
				self.crossOverEvent()

			# update the previous state with the latest sign
			self.diffSignPrevious = (np.sign(self.dfr['ema diff'].iloc[-1]))

		# now lets do some anlysis on the ema diff and see if we want to place trades
		# let's set a threshold and place trades if the difference is greater than this threshold
		# this should help remove some of the noise

		if (self.dfr['ema diff'].iloc[-1] > emaThreshold) and (self.changeState == True):
			self.changeState = False # clear the flag to allow another changeState event
			self.goLong = True
			print("go Long",self.goLong)
			self.openTrade(self.goLong)
		elif (self.dfr['ema diff'].iloc[-1] < -emaThreshold) and (self.changeState == True):
			self.changeState = False # clear the flag to allow another changeState event
			self.goLong = False
			print("go Short",self.goLong)
			self.openTrade(self.goLong)

	def crossOverEvent(self):
		# set data to None as we don't need to send anything, we just want the defaults to work correctly
		self.data = None

		# create the close trade statement
		trade = trades.TradeClose(accountID=account_id, tradeID=self.tradeID, data=self.data)
				
		# Check to see if we have an open trade, if we do then close it
		if (self.openTrades != 0) and (self.unrealizedPL > takeProfitMin):
			response = client.request(trade)

			print("Found a profitable trade, so lets close it -->",self.tradeID)
			print("This trade made £",self.unrealizedPL)
		else:
			print("No profitable trades I guess. Last trade was:",self.tradeID)
		
		print("trade placed at",self.dfr['time'].iloc[-1])
		

		#x_values.append(next(self.index)) #(self.dfr['time']))
		#y_values.append(dfr['closeoutAsk'].iloc[-1])#random.randint(0,10))
		#y_values.append(dfr['ema diff'].iloc[-1])#random.randint(0,10))
		#y2_values.append(dfr['ema fast'].iloc[-1])#random.randint(0,10))
		#y3_values.append(dfr['ema slow'].iloc[-1])#random.randint(0,10))
		#plt.cla()
		#plt.plot(x_values, y_values)
		#plt.plot(x_values, y2_values)
		#plt.plot(x_values, y3_values)

		#plt.show()
		

	def momentum(self, dfr):

		#print("momentum")
		# calculates the log returns from one tick to the next
		dfr['returns'] = np.log(dfr['closeoutAsk'] / dfr['closeoutAsk'].shift(1))
		
		# derives the positioning according to the momentum strategy
		dfr['position'] = np.sign(dfr['returns'].rolling(self.movingAverage).mean())

		print("position=",dfr['position'].iloc[-1])
		
		#print("number of open trades: ",self.openTrades)
		
		#print(dfr)

		# what the moving average analysis results in
		if (dfr['position'].iloc[-1] == 1) and (self.openTrades == 0):
			print("go long")
			self.goLong = True
			#self.openTrade(self.goLong)
		elif (dfr['position'].iloc[-1] == -1) and (self.openTrades == 0):
			print("go short")
			self.goLong = False
			#self.openTrade(self.goLong)

main = mainLoop(lotSize, movingAverage, emaFast, emaSlow, df)