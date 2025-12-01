import cv2
import json
import numpy as np
from pathlib import Path
import sys

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
from hand_detector import HandDetector
from websocket_server import WebSocketServer

# ============================================
# CHOOSE YOUR CALIBRATION PROFILE HERE
# ============================================
CALIBRATION_PROFILE = "gabriel"  # Change this to switch profiles
# ============================================

class HandTracker:
    """Main tracker - loads calibration, normalizes data, applies linearization"""
    
    def __init__(self, calibration_profile):
        # Load calibration
        calibration_path = Path("calibrations") / f"{calibration_profile}.json"
        if not calibration_path.exists():
            raise FileNotFoundError(f"Calibration '{calibration_profile}' not found!")
        
        with open(calibration_path, 'r') as f:
            self.config = json.load(f)
        
        print(f"Loaded calibration: {calibration_profile}")
        print(f"  Horizontal: {self.config['min_horizontal']:.1f} - {self.config['max_horizontal']:.1f}")
        print(f"  Vertical: {self.config['min_vertical']:.1f} - {self.config['max_vertical']:.1f}")
        print(f"  Neutral: {self.config['neutral_vertical']:.1f}")
        print(f"  H Linearization: {self.config['horizontal_linearization']['type']}")
        print(f"  V Linearization: {self.config['vertical_linearization']['type']}\n")
        
        self.detector = HandDetector()
        self.smooth_alpha = self.config.get('smooth_alpha', 0.2)
        
        # Smoothing state
        self.norm_smooth = None
        self.height_smooth = None
    
    def apply_linearization(self, raw_value, linearization_config):
        """Apply linearization function to raw value"""
        lin_type = linearization_config['type']
        
        if lin_type == 'linear':
            slope = linearization_config.get('slope', 1.0)
            intercept = linearization_config.get('intercept', 0.0)
            return slope * raw_value + intercept
        
        elif lin_type == 'polynomial':
            coeffs = linearization_config.get('coefficients', [0, 1])
            result = 0.0
            for i, coef in enumerate(coeffs):
                result += coef * (raw_value ** i)
            return result
        
        return raw_value
    
    def normalize_horizontal(self, raw_distance):
        """Normalize horizontal spread to 0..1"""
        min_h = self.config['min_horizontal']
        max_h = self.config['max_horizontal']
        
        # Normalize to 0..1
        normalized = (raw_distance - min_h) / (max_h - min_h)
        normalized = max(0.0, min(1.0, normalized))
        
        # Apply linearization
        linearized = self.apply_linearization(normalized, self.config['horizontal_linearization'])
        linearized = max(0.0, min(1.0, linearized))
        
        # Smooth
        if self.norm_smooth is None:
            self.norm_smooth = linearized
        else:
            self.norm_smooth = self.smooth_alpha * linearized + (1 - self.smooth_alpha) * self.norm_smooth
        
        return self.norm_smooth
    
    def normalize_vertical(self, raw_height):
        """Normalize vertical height to -1..+1 (relative to neutral)"""
        neutral = self.config['neutral_vertical']
        min_v = self.config['min_vertical']
        max_v = self.config['max_vertical']
        
        # Determine range from neutral
        if raw_height < neutral:
            # Below neutral: map min_v..neutral to +1..0 (hands high = positive)
            range_size = neutral - min_v
            normalized = (raw_height - neutral) / range_size if range_size > 0 else 0.0
        else:
            # Above neutral: map neutral..max_v to 0..-1 (hands low = negative)
            range_size = max_v - neutral
            normalized = (raw_height - neutral) / range_size if range_size > 0 else 0.0
        
        # INVERT: hands up (small Y) should be positive
        normalized = -normalized
        normalized = max(-1.0, min(1.0, normalized))
        
        # Apply linearization
        linearized = self.apply_linearization(normalized, self.config['vertical_linearization'])
        linearized = max(-1.0, min(1.0, linearized))
        
        # Smooth
        if self.height_smooth is None:
            self.height_smooth = linearized
        else:
            self.height_smooth = self.smooth_alpha * linearized + (1 - self.smooth_alpha) * self.height_smooth
        
        return self.height_smooth
    
    def process_frame(self, frame):
        """Process frame and return normalized values"""
        result = self.detector.process_frame(frame)
        
        output = {
            'valid': result['valid'],
            'distance_normalized': None,
            'height_normalized': None,
            'hand_landmarks': result['hand_landmarks'],
            'centers': result['centers'],
            'raw_distance': result['distance_raw'],
            'raw_height': result['height_raw']
        }
        
        if result['valid']:
            output['distance_normalized'] = self.normalize_horizontal(result['distance_raw'])
            output['height_normalized'] = self.normalize_vertical(result['height_raw'])
        
        return output
    
    def release(self):
        """Clean up resources"""
        self.detector.release()

def main():
    print("=== Hand Tracking for Drone Swarm Control ===\n")
    
    # Initialize tracker
    try:
        tracker = HandTracker(CALIBRATION_PROFILE)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run calibration_tool.py first!")
        return
    
    # Initialize WebSocket server
    ws_server = WebSocketServer(port=9052)
    ws_server.start()
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return
    
    print("Starting tracking... Press 'q' to quit\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process frame
        result = tracker.process_frame(frame)
        
        # Draw visualization
        if result['valid']:
            tracker.detector.draw_hands(frame, result['hand_landmarks'], result['centers'])
            
            # Send to Unity
            ws_server.send_data(
                distance=result['distance_normalized'],
                height=result['height_normalized']
            )
            
            # Display values
            cv2.putText(frame, f"Spread: {result['distance_normalized']:.3f} (0..1)", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            cv2.putText(frame, f"Height: {result['height_normalized']:.3f} (-1..+1)", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Raw: {result['raw_distance']:.1f}px, {result['raw_height']:.1f}px", 
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            cv2.putText(frame, f"Unity clients: {ws_server.get_client_count()}", 
                       (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "Show BOTH hands at similar distance from camera", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        cv2.putText(frame, f"Profile: {CALIBRATION_PROFILE} | Press 'q' to quit", 
                   (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        cv2.imshow("Hand Tracker - Drone Control", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    tracker.release()
    ws_server.stop()
    print("\nShutdown complete")

if __name__ == "__main__":
    main()