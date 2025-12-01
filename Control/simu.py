import pygame
import asyncio
import websockets
import json
import threading
from pathlib import Path

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
RED = (255, 100, 100)
GREEN = (100, 255, 100)
BLUE = (100, 150, 255)

class DroneSimulation:
    """Simple 2-ball simulation to test hand tracking"""
    
    def __init__(self, width=800, height=600):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Hand Tracking Test - Two Ball Simulation")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Tracking data
        self.distance = 0.5  # 0.0 to 1.0
        self.height_value = 0.0    # -1.0 to +1.0 (renamed to avoid confusion with window height)
        self.connected = False
        
        # Ball parameters
        self.ball_radius = 30
        self.center_x = width // 2
        self.center_y = height // 2
        
        # Animation smoothing
        self.target_distance = 0.5
        self.target_height_value = 0.0
        self.smooth_factor = 0.15
        
    def update_tracking_data(self, distance, height):
        """Update tracking values from WebSocket"""
        self.target_distance = distance
        self.target_height_value = height
        self.connected = True
    
    def smooth_values(self):
        """Smooth the transitions"""
        self.distance += (self.target_distance - self.distance) * self.smooth_factor
        self.height_value += (self.target_height_value - self.height_value) * self.smooth_factor
    
    def draw_balls(self):
        """Draw the two balls based on distance and height"""
        # Calculate positions
        max_separation = self.width * 0.4  # Maximum distance apart
        separation = self.distance * max_separation
        
        # Height: -1 (bottom) to +1 (top)
        # Map to screen coordinates (inverted because y=0 is top)
        # self.height is the window height (600), self.height_value is tracking (-1 to +1)
        max_height_range = (self.height - 100) * 0.35  # Use 35% of screen height with margin
        height_offset = -self.height_value * max_height_range  # Negative because screen Y is inverted
        y_pos = self.center_y + height_offset
        
        # Ball positions
        ball1_x = int(self.center_x - separation / 2)
        ball2_x = int(self.center_x + separation / 2)
        ball_y = int(y_pos)
        
        # Clamp to screen with margin
        margin = self.ball_radius + 20
        ball_y = max(margin, min(self.height - margin, ball_y))
        
        # Draw connection line
        pygame.draw.line(self.screen, WHITE, (ball1_x, ball_y), (ball2_x, ball_y), 2)
        
        # Draw balls
        pygame.draw.circle(self.screen, RED, (ball1_x, ball_y), self.ball_radius)
        pygame.draw.circle(self.screen, BLUE, (ball2_x, ball_y), self.ball_radius)
        
        # Draw glow effect
        for i in range(3):
            alpha_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            glow_radius = self.ball_radius + 10 + i * 8
            glow_alpha = 30 - i * 8
            pygame.draw.circle(alpha_surface, (*RED, glow_alpha), (ball1_x, ball_y), glow_radius)
            pygame.draw.circle(alpha_surface, (*BLUE, glow_alpha), (ball2_x, ball_y), glow_radius)
            self.screen.blit(alpha_surface, (0, 0))
    
    def draw_ui(self):
        """Draw UI elements"""
        # Title
        title = self.font.render("Hand Tracking Test", True, CYAN)
        self.screen.blit(title, (20, 20))
        
        # Connection status
        status_color = GREEN if self.connected else RED
        status_text = "CONNECTED" if self.connected else "WAITING FOR TRACKER..."
        status = self.small_font.render(status_text, True, status_color)
        self.screen.blit(status, (20, 60))
        
        # Values display
        distance_text = self.small_font.render(f"Spread: {self.distance:.3f} (0.0 - 1.0)", True, WHITE)
        height_text = self.small_font.render(f"Height: {self.height_value:.3f} (-1.0 - +1.0)", True, WHITE)
        self.screen.blit(distance_text, (20, 100))
        self.screen.blit(height_text, (20, 130))
        
        # Instructions
        instructions = [
            "Controls:",
            "- Spread hands apart -> Balls move apart",
            "- Bring hands together -> Balls move together",
            "- Raise hands -> Balls move up",
            "- Lower hands -> Balls move down",
            "",
            "Press ESC to quit"
        ]
        
        y_offset = self.height - 160
        for line in instructions:
            text = self.small_font.render(line, True, (150, 150, 150))
            self.screen.blit(text, (20, y_offset))
            y_offset += 22
        
        # Reference lines
        # Center horizontal line
        pygame.draw.line(self.screen, (50, 50, 50), (0, self.center_y), (self.width, self.center_y), 1)
        # Center vertical line
        pygame.draw.line(self.screen, (50, 50, 50), (self.center_x, 0), (self.center_x, self.height), 1)
        
        # Height indicators
        top_y = 50
        bottom_y = self.height - 50
        pygame.draw.line(self.screen, (80, 80, 80), (self.width - 50, top_y), (self.width - 30, top_y), 2)
        pygame.draw.line(self.screen, (80, 80, 80), (self.width - 50, self.center_y), (self.width - 30, self.center_y), 2)
        pygame.draw.line(self.screen, (80, 80, 80), (self.width - 50, bottom_y), (self.width - 30, bottom_y), 2)
        
        top_label = self.small_font.render("+1", True, (100, 100, 100))
        mid_label = self.small_font.render("0", True, (100, 100, 100))
        bot_label = self.small_font.render("-1", True, (100, 100, 100))
        self.screen.blit(top_label, (self.width - 80, top_y - 10))
        self.screen.blit(mid_label, (self.width - 80, self.center_y - 10))
        self.screen.blit(bot_label, (self.width - 80, bottom_y - 10))
    
    def run(self):
        """Main simulation loop"""
        running = True
        
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
            
            # Update
            self.smooth_values()
            
            # Draw
            self.screen.fill(BLACK)
            self.draw_balls()
            self.draw_ui()
            
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS
        
        pygame.quit()


class WebSocketClient:
    """WebSocket client to receive tracking data"""
    
    def __init__(self, simulation, port=9052):
        self.simulation = simulation
        self.port = port
        self.running = False
    
    async def connect(self):
        """Connect to WebSocket server and receive data"""
        uri = f"ws://localhost:{self.port}"
        
        while self.running:
            try:
                print(f"Connecting to tracker at {uri}...")
                async with websockets.connect(uri) as websocket:
                    print("✓ Connected to tracker!")
                    
                    while self.running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            data = json.loads(message)
                            
                            distance = data.get('distance', 0.5)
                            height = data.get('height', 0.0)
                            
                            self.simulation.update_tracking_data(distance, height)
                            
                        except asyncio.TimeoutError:
                            continue
                        except json.JSONDecodeError:
                            print("Warning: Invalid JSON received")
                            continue
                            
            except (ConnectionRefusedError, OSError):
                print("Waiting for tracker... (Make sure tracker.py is running)")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(2)
    
    def start(self):
        """Start WebSocket client in background thread"""
        self.running = True
        
        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.connect())
        
        thread = threading.Thread(target=run_async_loop, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop WebSocket client"""
        self.running = False


def main():
    print("=== Hand Tracking Two-Ball Simulation ===\n")
    print("Instructions:")
    print("  1. Make sure you have a calibration file (gabriel.json)")
    print("  2. Run tracker.py in another terminal")
    print("  3. This simulation will connect automatically")
    print("  4. Move your hands and watch the balls react!\n")
    print("Starting simulation...\n")
    
    # Create simulation
    sim = DroneSimulation(width=800, height=600)
    
    # Start WebSocket client
    ws_client = WebSocketClient(sim, port=9052)
    ws_client.start()
    
    # Run simulation
    try:
        sim.run()
    finally:
        ws_client.stop()
        print("\nSimulation closed")


if __name__ == "__main__":
    main()