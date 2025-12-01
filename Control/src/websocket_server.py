import asyncio
import websockets
import json
import threading
import queue

class WebSocketServer:
    """WebSocket server for sending tracking data to Unity"""
    
    def __init__(self, host="localhost", port=9052):
        self.host = host
        self.port = port
        self.connected_clients = set()
        self.message_queue = queue.Queue()
        self.server_thread = None
        self.loop = None
    
    async def handle_client(self, websocket):
        """Handle WebSocket connection from Unity"""
        self.connected_clients.add(websocket)
        print(f"Unity client connected. Total clients: {len(self.connected_clients)}")
        
        try:
            while True:
                # Check for messages to send (non-blocking)
                try:
                    message = self.message_queue.get_nowait()
                    await websocket.send(message)
                except queue.Empty:
                    pass
                
                # Small delay to prevent busy-waiting
                await asyncio.sleep(0.01)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.remove(websocket)
            print(f"Unity client disconnected. Total clients: {len(self.connected_clients)}")
    
    async def run_server(self):
        """Start WebSocket server"""
        server = await websockets.serve(self.handle_client, self.host, self.port)
        print(f"WebSocket server started on ws://{self.host}:{self.port}")
        await server.wait_closed()
    
    def _run_event_loop(self):
        """Run asyncio event loop in background thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_server())
    
    def start(self):
        """Start server in background thread"""
        self.server_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.server_thread.start()
    
    def send_data(self, distance, height):
        """Send normalized tracking data to Unity"""
        if len(self.connected_clients) == 0:
            return  # No clients connected
        
        message = json.dumps({
            "distance": round(distance, 4),
            "height": round(height, 4)
        })
        
        self.message_queue.put(message)
    
    def get_client_count(self):
        """Get number of connected Unity clients"""
        return len(self.connected_clients)
    
    def stop(self):
        """Stop the server"""
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)