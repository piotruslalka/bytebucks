import logging
import config as config

from gdax.authenticated_client import AuthenticatedClient
from decimal import Decimal

# Logging Settings
logger = logging.getLogger('botLog')


class MyFillOrderBook(AuthenticatedClient):
    """ This is where I store all my order and fill information """

    def __init__(self, key, b64secret, passphrase, strategy_settings):
        super(MyFillOrderBook, self).__init__(key=key, b64secret=b64secret, passphrase=passphrase)

        logger.info("Entered into the MyFillOrderBook Class!")

        self.my_buy_fills = []
        self.my_sell_fills = []
        self.my_buy_orders = []
        self.my_sell_orders = []
        self.my_buy_order_acks = []
        self.my_sell_order_acks = []
        self.pnl = 0
        self.net_position = 0
        self.real_position = 0
        self.product_id = strategy_settings.get('product_id')
        self.strategy_name = strategy_settings.get('strategy_name')
        self.order_size = strategy_settings.get('order_size')
        self.fill_notifications = strategy_settings.get('fill_notifications')
        self.place_notifications = strategy_settings.get('place_notifications')
        self.buy_levels = 0
        self.sell_levels = 0
        self.sent_buy_cancel = False
        self.sent_sell_cancel = False
        self.num_buy_cancel_rejects = 0
        self.num_sell_cancel_rejects = 0
        self.last_buy_price = 1000000
        self.last_sell_price = 0
        self.current_trade_price = 0

    def place_my_limit_order(self, side, price, size='0.01'):
        """ I place the limit order here """
        if(config.debug):
            return (True)

        str_price = str(round(float(price), 2))
        str_size = str(round(float(size), 8))

        logger.warning("We are placing an Order at:" + str_price)

        if side=='buy':
            my_order = self.buy(product_id=self.product_id, price=str_price, size=str_size, time_in_force='GTC', post_only=True)
        elif side=='sell':
            my_order = self.sell(product_id=self.product_id, price=str_price, size=str_size, time_in_force='GTC', post_only=True)
        else:
            #Sent order place without side!
            logging.critical("Invalid order side! " + side)
            return (False)

        logger.debug(my_order)

        # Check if limit order Rejected
        if 'status' in my_order:
            if my_order['status'] == 'rejected':
                logging.critical("ORDER REJECTED!")
                return (False)
            else:
                logging.debug("Saving Order...")
                if (side == "buy"):
                    self.my_buy_orders.append(self.clean_message(my_order))
                else:
                    self.my_sell_orders.append(self.clean_message(my_order))
                return (True)

        else:
            logger.error("status is not in my_order")
            logger.error(my_order)
            return (False)

    def clean_message(self, message):
        if 'price' in message:
            message['price'] = float(message['price'])
        if 'size' in message:
            message['size'] = float(message['size'])
        return message

    def add_my_order_ack(self, message):
        """ Add Order Ack to Order Ack Book """

        if message['side'] == 'buy':
            self.sent_buy_cancel=False
            self.my_buy_order_acks.append(self.clean_message(message))
        elif message['side'] == 'sell':
            self.sent_sell_cancel=False
            self.my_sell_order_acks.append(self.clean_message(message))
        else:
            logger.critical("Message has a side other than buy or sell in add_my_order_ack.")
            logger.critical(message)

    def process_cancel_message(self, message):
        """ Process the cancel message and remove orders from book if necessary. """

        if message['side'] == 'buy':
            if len(self.my_buy_orders) > 0:
                if message['order_id'] == self.my_buy_orders[0]['id']:
                    self.my_buy_orders.clear()
                    self.sent_buy_cancel = False
                    self.num_buy_cancel_rejects = 0
                    logger.debug("Setting Sent Buy Cancel to False")
                    logger.debug(self.my_buy_orders)
                else:
                    logger.critical("Message order_id: " + message['order_id'] + " does not match the id we have in my_buy_orders: " + self.my_buy_orders[0]['id'])
            #else:
            #    logger.critical("Canceling a buy order that did not originally exist in the buy order book. This is only okay if it was a manual fill.")
        elif message['side'] == 'sell':
            if len(self.my_sell_orders) > 0:
                if message['order_id'] == self.my_sell_orders[0]['id']:
                    self.my_sell_orders.clear()
                    self.sent_sell_cancel = False
                    self.num_sell_cancel_rejects = 0
                    logger.debug("Setting Sent Sell Cancel to False")
                    logger.debug(self.my_sell_orders)
                else:
                    logger.critical("Message order_id: " + message['order_id'] + " does not match the id we have in my_sell_orders: " + self.my_sell_orders[0]['id'])
            #else:
            #    logger.critical("Canceling a sell order that did not originally exist in the sell order book. This is only okay if it was a manual fill.")
        else:
            logger.critical("We have a message with side other than Buy or Sell in process cancel message.")
            logger.critical(message)

    def process_fill_message(self, message):
        """ Process the fill message and update positions and theos as necessary. """

        if message['side'] == 'buy':
            fill_size = message['size']
            remaining_size = self.my_buy_orders[0]['size'] - fill_size
            if remaining_size > 0.1*self.order_size:
                self.pnl -= fill_size * message['price']
                self.buy_levels += fill_size
                self.real_position += fill_size
                self.net_position = round(self.real_position / self.order_size)
                self.my_buy_orders[0]['size'] = remaining_size
            else:
                self.pnl -= self.my_buy_orders[0]['size'] * message['price']
                self.buy_levels += self.my_buy_orders[0]['size']
                self.real_position += self.my_buy_orders[0]['size']
                self.net_position = round(self.real_position / self.order_size)
                self.last_buy_price = message['price']
                self.last_sell_price = 0
                self.my_buy_orders.clear()

        elif message['side'] == 'sell':
            fill_size = message['size']
            remaining_size = self.my_sell_orders[0]['size'] - fill_size
            if remaining_size > 0.1*self.order_size:
                self.pnl += fill_size * message['price']
                self.sell_levels += fill_size
                self.real_position -= fill_size
                self.net_position = round(self.real_position / self.order_size)
                self.my_sell_orders[0]['size'] = remaining_size
            else:
                self.pnl += self.my_sell_orders[0]['size'] * message['price']
                self.sell_levels += self.my_sell_orders[0]['size']
                self.real_position -= self.my_sell_orders[0]['size']
                self.net_position = round(self.real_position / self.order_size)
                self.last_buy_price = 1000000
                self.last_sell_price = message['price']
                self.my_sell_orders.clear()

        else:
            logger.critical("Message Side is not either buy or sell in process fill message.")
            logger.critical(message)

    def verify_orders(self):
        if (len(self.my_buy_orders) >= 1):
            order_info = self.get_order(self.my_buy_orders[0]['id'])
            if(len(order_info)!=1):
                if(order_info['filled_size']!='0.00000000'):
                    remaining_size = round(float(order_info['size']) - float(order_info['filled_size']),8)
                    if(remaining_size <= 0.001):
                        #Order is completely filled.
                        logger.critical("Bid order is completely filled. (Missed fill message?)")
                        self.pnl -= self.my_buy_orders[0]['size'] * self.my_buy_orders[0]['price']
                        self.buy_levels += self.my_buy_orders[0]['size']
                        self.real_position += self.my_buy_orders[0]['size']
                        self.net_position = round(self.real_position / self.order_size)
                        self.last_buy_price = self.my_buy_orders[0]['price']
                        self.last_sell_price = 0
                        self.my_buy_orders.clear()
                    elif((remaining_size - round(self.my_buy_orders[0]['size'],8)) > 0.00000001):
                        logger.critical("Bid order is partially filled. (Missed Portion?)")
                        fill_size = self.my_buy_orders[0]['size'] - remaining_size
                        self.pnl -= fill_size * self.my_buy_orders[0]['price']
                        self.buy_levels += fill_size
                        self.real_position += fill_size
                        self.net_position = round(self.real_position / self.order_size)
                        self.my_buy_orders[0]['size'] = remaining_size
                    elif(order_info['status'] == 'done'):
                        #Order has been marked as complete.
                        logger.critical("Current Bid order is marked as complete with no missed volume. Removing from dictionary.")
                        self.my_buy_orders.clear()
                    else:
                        #Order appears to be currently valid.
                        logger.critical("Current Bid order with partial fills is valid.")
                elif(order_info['status'] == 'done'):
                    #Order has been marked as complete.
                    logger.critical("Current Bid order is marked as complete with no filled volume. Removing from dictionary.")
                    self.my_buy_orders.clear()
                else:
                    #Order appears to be currently valid.
                    logger.critical("Current Bid order is valid.")
            else:
                #This is likely a major problem!
                logger.critical("Order is not valid:" + self.my_buy_orders[0]['id'])
                logger.critical(order_info)
                self.my_buy_orders.clear()

        if (len(self.my_sell_orders) >= 1):
            order_info = self.get_order(self.my_sell_orders[0]['id'])
            if(len(order_info)!=1):
                if(order_info['filled_size']!='0.00000000'):
                    remaining_size = round(float(order_info['size']) - float(order_info['filled_size']),8)
                    if(remaining_size <= 0.001):
                        #Order is completely filled.
                        logger.critical("Ask order is completely filled. (Missed fill message?)")
                        self.pnl += self.my_sell_orders[0]['size'] * self.my_sell_orders[0]['price']
                        self.sell_levels += self.my_sell_orders[0]['size']
                        self.real_position -= self.my_sell_orders[0]['size']
                        self.net_position = round(self.real_position / self.order_size)
                        self.last_buy_price = 1000000
                        self.last_sell_price = self.my_sell_orders[0]['price']
                        self.my_sell_orders.clear()
                    elif((remaining_size - round(self.my_sell_orders[0]['size'],8)) > 0.00000001):
                        logger.critical("Bid order is partially filled. (Missed Portion?)")
                        fill_size = self.my_sell_orders[0]['size'] - remaining_size
                        self.pnl += fill_size * self.my_sell_orders[0]['price']
                        self.sell_levels += fill_size
                        self.real_position -= fill_size
                        self.net_position = round(self.real_position / self.order_size)
                        self.my_sell_orders[0]['size'] = remaining_size
                    elif(order_info['status'] == 'done'):
                        #Order has been marked as complete.
                        logger.critical("Current Bid order is marked as complete with no missed volume. Removing from dictionary.")
                        self.my_sell_orders.clear()
                    else:
                        #Order appears to be currently valid.
                        logger.critical("Current Bid order with partial fills is valid.")
                elif(order_info['status'] == 'done'):
                    #Order has been marked as complete.
                    logger.critical("Current Bid order is marked as complete with no filled volume. Removing from dictionary.")
                    self.my_sell_orders.clear()
                else:
                    #Order appears to be currently valid.
                    logger.critical("Current Bid order is valid.")
            else:
                #This is likely a major problem!
                logger.critical("Order is not valid:" + self.my_sell_orders[0]['id'])
                logger.critical(order_info)
                self.my_sell_orders.clear()

    # def add_my_fill(self, fill):
    #     """ Add Fill to book """
    #     logging.warning("Adding Fill to book")
    #     logging.warning(fill)
    #
    #     if fill['side'] == 'buy':
    #         # Add to Fills list
    #         self.my_buy_fills.append(fill)
    #         # Remove from Orders list
    #         for order in self.my_buy_orders:
    #             if fill['maker_order_id'] in order.keys():
    #                 self.my_buy_orders.remove(order)
    #                 logging.warning("Removing " + str(fill['maker_order_id']) + " from Buy Order Book.")
    #                 logging.warning(self.my_buy_orders)
    #
    #     if fill['side'] == 'sell':
    #         # Add to Fills list
    #         self.my_sell_fills.append(fill)
    #         # Remove from Orders list
    #         for order in self.my_sell_orders:
    #             if fill['maker_order_id'] in order.keys():
    #                 self.my_sell_orders.remove(order)
    #                 logging.warning("Removing " + str(fill['maker_order_id']) + " from Sell Order Book.")
    #                 logging.warning(self.my_sell_orders)
    #
    #
    #     logging.info("Number of Open Buy Fills: " + str(len(self.my_buy_fills)))
    #     logging.info("Number of Open Sell Fills: " + str(len(self.my_sell_fills)))
    #     print("Number of Open Buy Fills: " + str(len(self.my_buy_fills)))
    #     print("Number of Open Sell Fills: " + str(len(self.my_sell_fills)))
    #
    #     # Now that we have a fill. Lets place a profit order
