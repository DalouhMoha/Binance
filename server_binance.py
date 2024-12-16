import json
import requests
import time
import asyncio
import websockets

session = requests.Session()
clients = set()
result = {}
precisions = {}
def get_last_price():
    url = f"https://api.binance.com/api/v3/ticker/price"
    try:
        response = session.get(url)
        data = response.json()
        print(data)
        prices_dict = {item['symbol']: item['price'] for item in data}
        # print(prices_dict)
        
        return prices_dict
    except Exception as e :
        print(f"error in getting last price : {e}")
def get_precision():
    url = f"https://api.binance.com/api/v3/exchangeInfo"
    try:
        response = session.get(url)
        exchange_info = response.json()

        precision_dict = {}
        
        # Find the symbol information in the response
        for symbol_info in exchange_info['symbols']:
            symbol = symbol_info['symbol']
            price_precision = int(symbol_info['filters'][0]['tickSize'].index('1') - 1)
            quantity_precision = int(symbol_info['filters'][1]['stepSize'].index('1') - 1)
            precision_dict[symbol] = {'price_precision': price_precision, 'quantity_precision': quantity_precision}

        return precision_dict 
    except Exception as e :
        print(f"error in getting precisions :{e}")
#server of the data
async def send_data_to_clients():

    while True:
        try:
            last_price =get_last_price()
            precisions = get_precision()

            # Get precision and last price data
            if isinstance(last_price, dict) and isinstance(precisions, dict) and last_price and precisions:
                
                    payload = {
                            "last_price": last_price,
                            "precisions": precisions
                    }
                    payload_json = json.dumps(payload)
                    
                    print(f"send data to client at {int(time.time() * 1000)}")
                    await asyncio.gather(*[client.send(payload_json) for client in clients])
  
        except Exception as e:
                print(f"Error sending data to clients: {e}")
        await asyncio.sleep(5)  

async def client_handler(websocket, path):
    clients.add(websocket)
    try:
        await websocket.wait_closed()  
    finally:
        clients.remove(websocket)
   

async def main():
    server = await websockets.serve(client_handler, "localhost", 9877)
    await server.wait_closed()

async def run_tasks():
    try:
        await asyncio.gather(main(), send_data_to_clients())
    except Exception as e:
        print(f"RELAY TOA ERROR: {e}")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(run_tasks())
        except Exception as e:
            print(f"Unexpected error outside the event loop: {e}")
        time.sleep(5)