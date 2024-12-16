import asyncio
import websockets
import json
import time
import requests
from bs4 import BeautifulSoup

# Store connected clients
connected_clients = set()

# Binance URL and headers
BINANCE_URL = "https://www.binance.com/en/support/announcement/new-cryptocurrency-listing?c=48&navId=48&hl=en"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )
}

# Keep track of sent articles to avoid duplicates
sent_articles = set()


async def handle_connection(websocket, path):
    """Handle incoming WebSocket connections."""
    connected_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)


async def send_to_all_clients(message):
    """Send a message to all connected WebSocket clients."""
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients])


async def fetch_and_broadcast_news():
    """Fetch the latest Binance news and broadcast to clients if within the 5s range."""
    global sent_articles
    while True:
        try:
            # Fetch the Binance page
            response = requests.get(BINANCE_URL, headers=HEADERS)
            response.raise_for_status()

            # Parse the page content
            soup = BeautifulSoup(response.text, "html.parser")
            script_tag = soup.find("script", {"id": "__APP_DATA", "type": "application/json"})
            if not script_tag:
                print("Couldn't find the target script tag.")
                continue

            # Load JSON data
            json_data = json.loads(script_tag.string)
            articles = json_data["appState"]["loader"]["dataByRouteId"]["d9b2"]["catalogs"][0]["articles"]

            # Check and broadcast articles within 5 seconds
            current_time = int(time.time() * 1000)  # Current time in milliseconds
            for article in articles:
                release_date = article["releaseDate"]
                time_difference = abs(current_time - release_date)
                if time_difference <= 5000 and article["id"] not in sent_articles:
                    # Add to sent articles and broadcast
                    sent_articles.add(article["id"])
                    article["source"]="binance"
                    await send_to_all_clients(json.dumps(article))
                    print(f"Broadcasted article: {article}")

        except Exception as e:
            print(f"Error fetching or processing news: {e}")

        # Wait before fetching again
        await asyncio.sleep(10)


async def main():
    """Main function to start the WebSocket server and news fetcher."""
    # Start the WebSocket server
    server = await websockets.serve(handle_connection, "localhost", 8765)

    # Schedule tasks
    fetch_news_task = asyncio.create_task(fetch_and_broadcast_news())
    await asyncio.gather(server.wait_closed(), fetch_news_task)


if __name__ == "__main__":
    asyncio.run(main())
