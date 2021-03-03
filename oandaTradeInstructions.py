import oandapyV20
from oandapyV20 import API
from oandapyV20.contrib.requests import MarketOrderRequest
from oandapyV20.exceptions import V20Error, StreamTerminated

import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.accounts as accounts
from oandapyV20.endpoints.pricing import PricingStream

import pandas as pd
import numpy as np

class tradeManager():
    def __init__(self):
        pass

class MomentumTrader(PricingStream):
    # reset the trade counts for the session
    tradesPlaced = 0
    def __init__(self, momentum, data_frame, access_token, currencyPair, lotSize, *args, **kwargs): 
        PricingStream.__init__(self, *args, **kwargs)
        # Set class vars
        self.ticks = 0 
        self.position = 0
        self.df = data_frame.DataFrame()
        self.momentum = momentum
        self.units = lotSize
        self.connected = False
        self.client = oandapyV20.API(access_token=access_token)
        #API(access_token=config['oanda']['access_token'])

    # method to place a trade
    def create_order(self, units, account_id, currencyPair):
        order = orders.OrderCreate(accountID=account_id, data=MarketOrderRequest(instrument=currencyPair, units=units).data)
        response = self.client.request(order)
        MomentumTrader.tradesPlaced += 1
        print("create order ", order)
        print('\t', response)

    # method called on each tick received
    def on_success(self, data, accountID, currencyPair):
        account_id = accountID
        # increment number of ticks recieved in the session
        self.ticks += 1
        print("ticks=",self.ticks)
        # print(self.ticks, end=', ')
        
        # appends the new tick data to the DataFrame object
        self.df = self.df.append(pd.DataFrame([{'time': data['time'],'closeoutAsk':data['closeoutAsk']}],
                                 index=[data["time"]]))
        # transforms the time information to a DatetimeIndex object
        self.df.index = pd.DatetimeIndex(self.df["time"])
        
        # Convert items back to numeric (Why, OANDA, why are you returning strings?)
        self.df['closeoutAsk'] = pd.to_numeric(self.df["closeoutAsk"],errors='ignore')
        
        # resamples the data set to a new, homogeneous interval
        dfr = self.df.resample('5s').last().bfill()
        
        # calculates the log returns
        dfr['returns'] = np.log(dfr['closeoutAsk'] / dfr['closeoutAsk'].shift(1))        
        
        # derives the positioning according to the momentum strategy
        dfr['position'] = np.sign(dfr['returns'].rolling( 
                                      self.momentum).mean())
        
        print("position=",dfr['position'].iloc[-1])
        
        # check to see what the previous entries were
        if dfr['position'].iloc[-1] == 1:
            print("go long")
            if self.position == 0:
                self.create_order(self.units, account_id, currencyPair)
            elif self.position == -1:
                self.create_order(self.units, account_id, currencyPair)
            self.position = 1
        elif dfr['position'].iloc[-1] == -1:
            print("go short")
            if self.position == 0:
                self.create_order(-self.units, account_id, currencyPair)
            elif self.position == 1:
                self.create_order(-self.units, account_id, currencyPair)
            self.position = -1
        if self.ticks == 250000:
            print("close out the position 5 ")
            if self.position == 1:
                self.create_order(-self.units, account_id, currencyPair)
            elif self.position == -1:
                self.create_order(self.units, account_id, currencyPair)
            self.disconnect()
        print("Trades created", MomentumTrader.tradesPlaced)
    def disconnect(self):
        self.connected=False
    def rates(self, accountID, instruments, **params):
        self.connected = True
        params = params or {}
        ignore_heartbeat = None
        currencyPair = instruments
        account_id = accountID
        if "ignore_heartbeat" in params:
            ignore_heartbeat = params['ignore_heartbeat']
        while self.connected:
            response = self.client.request(self)
            for tick in response:
                if not self.connected:
                    break
                if not (ignore_heartbeat and tick["type"]=="HEARTBEAT"):
                    #print(tick)
                    self.on_success(tick, account_id, currencyPair)