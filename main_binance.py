import hashlib
import hmac
import json
import requests
import time
import asyncio
import websockets
import re

api_key = "XcNTqLn9JKiwICtZ7VI954iUEURyRkvxGYhs46hWAi4IkoUjGw3R6st5cax1r14Y"
secret_key = "HMXETRCbVI25QoZEQ0pWBKHH0cGDo1oCXKTbuC152Hb5saBQNtUzv2NXblQhwEOI"

session = requests.Session()

# Variables Section
timesleep = 20
warmup_interval = 5
investment = 16
slippage = 0.05
gain_percentage = 5
last_price_data = {}
precisions = {}
buy_side ="BUY"
sell_side = "SELL"

# Function to listen to WebSocket client for incoming messages 
async def listen_to_websocket():
    uri = "ws://localhost:8765"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                while True:
                    message = await websocket.recv()
                    print(f"received message at {int(time.time() * 1000)}")
                    print(f"Received message: {message}")

                    on_message(message)
        except Exception as e:
            print(f"Error in listen_to_websocket: {str(e)}")
        await asyncio.sleep(10)  
    
def on_message(message):


    on_message_start_time = time.time()
    print(f"Executing on_message: {message}")

    dict_data = json.loads(message)
    title = dict_data.get("title", "")
    source = dict_data.get("source", "")

    if "binance" in source.lower():
        # Extract tokens
        token1, token2 = extract_tokens(title)
        print(token1, " =========== ", token2)

        if token1:
            print("into token 1")
            asyncio.create_task(process_token(token1))

        if token2:
            print("into token 2")
            asyncio.create_task(process_token(token2))
            
        else:
            print("No token found in the message.")
                    
    on_message_end_time = time.time()
    on_message_execution_time = on_message_end_time - on_message_start_time
    print(f"on_message execution time: {on_message_execution_time} seconds")

def extract_tokens(title):
    patterns = [
        r"Binance Futures Will Launch (.*?) Perpetual Contract",
        r"Binance Futures Will Launch (.*?) and (.*?) Perpetual",
        r"Binance Will List (.*?)\((.*?)\)"
    ]

    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            groups = match.groups()
            return groups[-1], groups[0] if len(groups) > 1 else None
    return None, None


async  def process_token(token):
    global last_price_data
    global precisions
    global slippage  
    token1 = format_token(token)
    final_token_usdt = find_first_matching_token(token1, last_price_data.keys())
    print(final_token_usdt)
    token_price_precision = int(precisions[final_token_usdt]['price_precision'])
    token_quantity_precision = int(precisions[final_token_usdt]['quantity_precision'])
    token_quantity_precision = max(0, token_quantity_precision)  
    token_last_price = float(last_price_data[final_token_usdt])
     

    #printing price and precision
    print(f'{final_token_usdt} Price Precision: {token_price_precision}')
    print(f'{final_token_usdt} quantity precision: {token_quantity_precision}')
    print(f'{final_token_usdt} last price : {token_last_price}')
    final_price=calculate_buy_price(token_last_price, token_price_precision, slippage, buy_side)
    print("FINAL PRICE ",final_price)    
    quantity = calculate_quantity(final_price, investment,token_quantity_precision)
    print("quantity",quantity)
    limit_order = submit_limit_order(final_token_usdt,final_price,quantity,buy_side)
    print(limit_order)
    print(f"Submit order at {int(time.time() * 1000)}")
    commission = float(limit_order['fills'][0]['commission'])
    final_quantity  =subtract_commission(quantity, commission,token_quantity_precision)
    print(f"quantity after comission{final_quantity}")

    if 'code' not in limit_order and 'msg' not in limit_order:
        average_price = float(limit_order['cummulativeQuoteQty'])/float(limit_order['executedQty'])
        avg_price = float(average_price) 
        print("The average price is : ",avg_price)
        take_profit_price = calculate_take_profit(avg_price,buy_side , gain_percentage,token_price_precision)
        print("Take profit price : ",take_profit_price)

        submit_tp=submit_tp_order(final_token_usdt,take_profit_price,quantity,sell_side,token_quantity_precision)
        print(f"Submit TP at {int(time.time() * 1000)}")
        print(submit_tp)

    await asyncio.sleep(timesleep)
    for i in range(5):
        cancell(final_token_usdt)
        close = submit_market_order(final_token_usdt,final_quantity,sell_side)
        print(close)
        send_to_telegram(f"Close order at {int(time.time() * 1000)}")
        pass

def format_token(token):
 
     return token.split()[-1] + "USDT"
 
def find_first_matching_token(token, token_list):
    modified_token = token.lstrip('10')
    for list_token in token_list:
        list_token_without_numbers = ''.join(filter(lambda x: not x.isdigit(), list_token))
        if modified_token == list_token_without_numbers:
            return list_token

        

def calculate_buy_price(last_price, precision, slippage, side):
 
    
    if side.upper() == "BUY":
        price_quantity = last_price * (1 + slippage)
    else:
        price_quantity = last_price * (1 - slippage)
    
    if precision == 0:
        final_price = int(price_quantity)
    else:
        final_price = round(price_quantity, precision)
    
    return final_price
def subtract_commission(quantity, commission, precision):
    new_quantity = quantity - commission
    
    # Adjust the resulting quantity based on precision
    if precision == 0:
        return int(new_quantity)
    elif precision >= 1:
        return round(new_quantity - 0.05 / (10 ** (precision - 1)), precision)
    else:
        return new_quantity
def calculate_quantity(price, inv, precision):
    if precision == 0:
        final_quantity = int(inv / price)
    else:
        final_quantity = round(inv / price, precision)

    # Format the final_quantity as a string with the desired number of decimal places
    formatted_quantity = '{:.{}f}'.format(final_quantity, precision)
    
    return float(formatted_quantity)
def calculate_take_profit(avg_price, side,  gain_percentage, price_precision):

    if side == 'BUY':
        take_profit = avg_price * (1 + (gain_percentage / 100) )
    elif side == 'SELL':
        take_profit = avg_price * (1 - (gain_percentage / 100) )
    else:
        raise ValueError("Invalid side parameter")
    if price_precision == 0:
        tp = int(take_profit)
    else :    
        tp = round(take_profit,price_precision)  

    return tp
def get_last_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker?symbol={symbol}"
    response = session.get(url)
    data = response.json()
    try :
        last_price = float(data["lastPrice"])
        return last_price
    except Exception as e :
        print(f'error getting last price :{e}')
def submit_tp_order(symbol, price, quantity, side,precision):
    tp_quantity = quantity/2
    final_tp_quantity = round(tp_quantity,precision)
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'TAKE_PROFIT_LIMIT',
        "timeInForce":"GTC",
        'quantity': str(final_tp_quantity),
        "price":str(price),
        "stopPrice":str(price) ,
        'timestamp': str(int(time.time() * 1000)),  
    }
    try:
        query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
        signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params['signature'] = signature
        url = 'https://api.binance.com/api/v3/order?' + query_string + f'&signature={signature}'
        headers = {'X-MBX-APIKEY': api_key}
        response = session.post(url, headers=headers)

        return response.json()
    except Exception as e :
        print(f"error submtin order :{e}")

def submit_limit_order( symbol, price, quantity, side):
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'LIMIT',
        'timeInForce': 'GTC',
        'quantity': str(quantity),
        'price': str(price),
        'recvWindow': '5000',
        'timestamp': str(int(time.time() * 1000))  
    }
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature
    url = 'https://api.binance.com/api/v3/order?' + query_string + f'&signature={signature}'
    headers = {'X-MBX-APIKEY': api_key}
    try :
        response = session.post(url, headers=headers)
        return response.json()
    except Exception as e :
        print(f'error sending order :{e}')

def submit_market_order( symbol ,quantity, side):
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': str(quantity),
        'recvWindow': '5000',
        'timestamp': str(int(time.time() * 1000))  
    }
    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature
    url = 'https://api.binance.com/api/v3/order?' + query_string + f'&signature={signature}'
    headers = {'X-MBX-APIKEY': api_key}
    try:
        response = session.post(url, headers=headers)
        return response.json()
    except Exception as e :
        print(f"error submtin order market :{e}")
def cancell(symbol):
    params = {
        'symbol': symbol,
        'timestamp': str(int(time.time() * 1000))  
    }

    query_string = '&'.join([f"{key}={value}" for key, value in sorted(params.items())])
    signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params['signature'] = signature
    url = 'https://api.binance.com/api/v3/openOrders?' + query_string + f'&signature={signature}'
    headers = {'X-MBX-APIKEY': api_key}
    try :
        response = session.delete(url, headers=headers)
        return response.json()
    except Exception as e :
        print(f'error cancell order:{e}')

def send_to_telegram(msg):
    print(msg)
async def warmup_session():
    while True:
      try :
        btc_price = get_last_price("BTCUSDT")
        print(f"BTC PRICE :{btc_price}")
        await asyncio.sleep(5)
      except Exception as e:
          print(f'Warmup Execption:{e}')
          await asyncio.sleep(5) 
                
async def receive_data():
    global last_price_data
    global precisions
    uri = "ws://localhost:9877"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                while True:
                    data_json = await websocket.recv()
                    data = json.loads(data_json)
                    last_price_data = data.get("last_price")
                    precisions = data.get("precisions")
                    # print(last_price_data)
                    print(f"received data at {int(time.time() * 1000)}")
                    await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in receive_data: {str(e)}")
        await asyncio.sleep(5)  

# Main function
async def main():
    while True :    
        try:    
            tasks = [
                asyncio.create_task(receive_data()),
                asyncio.create_task(listen_to_websocket()),
                asyncio.create_task(warmup_session())    
            ]
            await asyncio.gather(*tasks)
        except Exception as e :
            print(f"Error in main:{e}")    
if __name__ == "__main__":
    asyncio.run(main())