import cv2
import json
import numpy as np
from pathlib import Path
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from hand_detector import HandDetector

def main():
    print("=== Hand Tracking Calibration Tool ===\n")
    
    # Get profile name
    profile_name = input("Enter calibration profile name (e.g., 'gabriel'): ").strip()
    if not profile_name:
        profile_name = "default"
    
    description = input("Description (optional): ").strip()
    
    print("\nStarting calibration...\n")
    print("Instructions:")
    print("  Show both hands to the camera")
    print("  A 5-second countdown will start automatically")
    print("  Hold your position during capture")
    print("  Press 'q' to quit\n")
    
    detector = HandDetector()
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return
    
    # Calibration state
    state = "min_horizontal"
    samples = {
        'min_horizontal': [],
        'max_horizontal': [],
        'min_vertical': [],
        'max_vertical': [],
        'neutral_vertical': []
    }
    
    state_messages = {
        'min_horizontal': "MINIMUM HAND SPREAD",
        'max_horizontal': "MAXIMUM HAND SPREAD",
        'min_vertical': "MINIMUM HEIGHT (LOW)",
        'max_vertical': "MAXIMUM HEIGHT (HIGH)",
        'neutral_vertical': "NEUTRAL HEIGHT (CENTER)",
        'done': "Calibration complete! Saving..."
    }
    
    state_instructions = {
        'min_horizontal': "Put your hands CLOSE together",
        'max_horizontal': "Put your hands FAR apart",
        'min_vertical': "Put your hands LOW (bottom of frame)",
        'max_vertical': "Put your hands HIGH (top of frame)",
        'neutral_vertical': "Put your hands at CENTER height",
    }
    
    countdown_start = None
    countdown_active = False
    capturing = False
    capture_count = 0
    SAMPLES_PER_POINT = 30
    COUNTDOWN_DURATION = 5.0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        result = detector.process_frame(frame)
        
        # Draw big step title
        if state != 'done':
            cv2.putText(frame, state_messages.get(state, ""), 
                       (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
            cv2.putText(frame, state_instructions.get(state, ""), 
                       (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        if result['valid']:
            detector.draw_hands(frame, result['hand_landmarks'], result['centers'])
            
            # Show raw values
            cv2.putText(frame, f"Spread: {result['distance_raw']:.1f}px", 
                       (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            cv2.putText(frame, f"Height: {result['height_raw']:.1f}px", 
                       (20, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            
            # Start countdown automatically when hands are detected
            if not countdown_active and not capturing and state != 'done':
                countdown_active = True
                countdown_start = time.time()
            
            # Countdown display
            if countdown_active and not capturing and state != 'done':
                elapsed = time.time() - countdown_start
                remaining = COUNTDOWN_DURATION - elapsed
                
                if remaining > 0:
                    # Big countdown number
                    countdown_num = int(remaining) + 1
                    cv2.putText(frame, str(countdown_num), 
                               (frame.shape[1]//2 - 50, frame.shape[0]//2), 
                               cv2.FONT_HERSHEY_SIMPLEX, 5.0, (0, 255, 0), 10)
                    
                    # Progress bar
                    bar_width = int((elapsed / COUNTDOWN_DURATION) * 400)
                    cv2.rectangle(frame, (frame.shape[1]//2 - 200, frame.shape[0]//2 + 100),
                                 (frame.shape[1]//2 - 200 + bar_width, frame.shape[0]//2 + 130),
                                 (0, 255, 0), -1)
                    cv2.rectangle(frame, (frame.shape[1]//2 - 200, frame.shape[0]//2 + 100),
                                 (frame.shape[1]//2 + 200, frame.shape[0]//2 + 130),
                                 (255, 255, 255), 2)
                else:
                    # Start capturing
                    capturing = True
                    countdown_active = False
                    print(f"Capturing {state}...")
            
            # Capture samples
            if capturing and state != 'done':
                if 'horizontal' in state:
                    samples[state].append(result['distance_raw'])
                else:
                    samples[state].append(result['height_raw'])
                
                capture_count += 1
                
                # Big "CAPTURING" text
                cv2.putText(frame, "CAPTURING...", 
                           (frame.shape[1]//2 - 200, frame.shape[0]//2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 5)
                
                # Progress
                cv2.putText(frame, f"{capture_count}/{SAMPLES_PER_POINT}", 
                           (frame.shape[1]//2 - 80, frame.shape[0]//2 + 80), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                
                if capture_count >= SAMPLES_PER_POINT:
                    capturing = False
                    capture_count = 0
                    countdown_active = False
                    print(f"✓ Captured {state}: {np.median(samples[state]):.1f}px")
                    
                    # Move to next state
                    if state == 'min_horizontal':
                        state = 'max_horizontal'
                    elif state == 'max_horizontal':
                        state = 'min_vertical'
                    elif state == 'min_vertical':
                        state = 'max_vertical'
                    elif state == 'max_vertical':
                        state = 'neutral_vertical'
                    elif state == 'neutral_vertical':
                        state = 'done'
        else:
            # Reset countdown if hands not detected
            countdown_active = False
            countdown_start = None
            
            cv2.putText(frame, "SHOW BOTH HANDS", 
                       (frame.shape[1]//2 - 220, frame.shape[0]//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
            cv2.putText(frame, "at similar distance from camera", 
                       (frame.shape[1]//2 - 250, frame.shape[0]//2 + 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        cv2.putText(frame, "Press 'q' to quit", 
                   (20, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        
        cv2.imshow("Calibration Tool", frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Calibration cancelled")
            break
        
        if state == 'done':
            # Compute final values
            min_vert_raw = float(np.median(samples['min_vertical']))
            max_vert_raw = float(np.median(samples['max_vertical']))
            
            # AUTO-FIX: Swap if needed (screen coords have Y=0 at top)
            if min_vert_raw > max_vert_raw:
                print(f"\n⚠️  Auto-fixing: Swapping min/max vertical (screen coords)")
                min_vert_raw, max_vert_raw = max_vert_raw, min_vert_raw
            
            calibration = {
                "profile_name": profile_name,
                "description": description,
                "min_horizontal": float(np.median(samples['min_horizontal'])),
                "max_horizontal": float(np.median(samples['max_horizontal'])),
                "min_vertical": min_vert_raw,
                "max_vertical": max_vert_raw,
                "neutral_vertical": float(np.median(samples['neutral_vertical'])),
                "smooth_alpha": 0.2,
                "horizontal_linearization": {
                    "type": "linear",
                    "slope": 1.0,
                    "intercept": 0.0
                },
                "vertical_linearization": {
                    "type": "linear",
                    "slope": 1.0,
                    "intercept": 0.0
                }
            }
            
            # Save to JSON
            Path("calibrations").mkdir(exist_ok=True)
            filepath = Path("calibrations") / f"{profile_name}.json"
            
            with open(filepath, 'w') as f:
                json.dump(calibration, f, indent=4)
            
            print(f"\n✓ Calibration saved to {filepath}")
            print(f"  min_horizontal: {calibration['min_horizontal']:.1f}")
            print(f"  max_horizontal: {calibration['max_horizontal']:.1f}")
            print(f"  min_vertical: {calibration['min_vertical']:.1f} (LOW)")
            print(f"  max_vertical: {calibration['max_vertical']:.1f} (HIGH)")
            print(f"  neutral_vertical: {calibration['neutral_vertical']:.1f}")
            
            break
    
    cap.release()
    cv2.destroyAllWindows()
    detector.release()

if __name__ == "__main__":
    main()