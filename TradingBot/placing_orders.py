
from decimal import Decimal
from gdax.authenticated_client import AuthenticatedClient
from MyFillOrderBook import MyFillOrderBook

import config

# Log my Keys
my_user_id = config.my_user_id
myKeys = config.live


auth_client = MyFillOrderBook(myKeys['key'], myKeys['secret'], myKeys['passphrase'])

#offset = 1
#close_price = '13423'

#my_ask = Decimal(close_price) + offset
#my_bid = Decimal(close_price) - offset



#auth_client.

order_details = "We have no working orders"

my_bid = Decimal(16000)

my_decimal_bid = Decimal(my_bid)

my_realbid = Decimal(my_decimal_bid)
#my_ask = 18000

my_order = auth_client.place_my_limit_order('buy', my_realbid, '0.02')
#my_order = auth_client.place_my_limit_order('sell', my_ask, '0.02')

if (len(auth_client.my_buy_orders) > 0):
    order_details = auth_client.my_buy_orders[0]
else:
    print("We have no working orders")
    
print(order_details)