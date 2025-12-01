import cv2
import json
import numpy as np
from pathlib import Path
import sys
import time
from sklearn.metrics import r2_score

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from hand_detector import HandDetector

def compute_polynomial_fit(samples, degree=3):
    """Compute polynomial regression"""
    if len(samples) < degree + 1:
        return compute_linear_fit(samples)
    
    X = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    
    # Polynomial fit
    coefficients = np.polyfit(X, y, degree)
    poly = np.poly1d(coefficients)
    
    # Compute quality metrics
    y_pred = poly(X)
    r_squared = r2_score(y, y_pred)
    errors = np.abs(y - y_pred)
    
    # Reverse coefficients for our format (c0 + c1*x + c2*x^2 + ...)
    coeffs_list = list(reversed(coefficients))
    
    return {
        "type": "polynomial",
        "coefficients": [float(c) for c in coeffs_list],
        "r_squared": float(r_squared),
        "max_error": float(np.max(errors)),
        "mean_error": float(np.mean(errors))
    }

def compute_linear_fit(samples):
    """Compute linear regression"""
    if len(samples) < 2:
        return {"type": "linear", "slope": 1.0, "intercept": 0.0}
    
    X = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    
    # Linear regression
    A = np.vstack([X, np.ones(len(X))]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    
    y_pred = slope * X + intercept
    r_squared = r2_score(y, y_pred)
    errors = np.abs(y - y_pred)
    
    return {
        "type": "linear",
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": float(r_squared),
        "max_error": float(np.max(errors)),
        "mean_error": float(np.mean(errors))
    }

def main():
    print("=== Linearization Tool - Automatic Mode ===\n")
    
    # Load existing calibration
    profile_name = input("Enter calibration profile name to update: ").strip()
    calibration_path = Path("calibrations") / f"{profile_name}.json"
    
    if not calibration_path.exists():
        print(f"Error: Calibration '{profile_name}' not found!")
        print("Please run calibration_tool.py first.")
        return
    
    with open(calibration_path, 'r') as f:
        calibration = json.load(f)
    
    print(f"\nLoaded calibration: {profile_name}")
    print(f"  Horizontal range: {calibration['min_horizontal']:.1f} - {calibration['max_horizontal']:.1f}")
    print(f"  Vertical range: {calibration['min_vertical']:.1f} - {calibration['max_vertical']:.1f}\n")
    
    print("This tool will guide you through 10 positions:")
    print("  - 5 horizontal positions (0%, 25%, 50%, 75%, 100%)")
    print("  - 5 vertical positions (0%, 25%, 50%, 75%, 100%)")
    print("\nFor each position:")
    print("  1. Position your hands")
    print("  2. Automatic 5-second countdown starts")
    print("  3. Hold steady during capture")
    print("  Press 'q' to quit anytime\n")
    
    input("Press ENTER to start...")
    
    detector = HandDetector()
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return
    
    # Sequence of positions to capture
    positions = [
        # Horizontal spread
        ("horizontal", 0.0, "MINIMUM SPREAD", "Put hands CLOSE together"),
        ("horizontal", 0.25, "25% SPREAD", "Put hands at 1/4 maximum spread"),
        ("horizontal", 0.5, "50% SPREAD", "Put hands at HALF maximum spread"),
        ("horizontal", 0.75, "75% SPREAD", "Put hands at 3/4 maximum spread"),
        ("horizontal", 1.0, "MAXIMUM SPREAD", "Put hands FAR apart"),
        
        # Vertical height
        ("vertical", 0.0, "MINIMUM HEIGHT", "Put hands at LOWEST position"),
        ("vertical", 0.25, "25% HEIGHT", "Put hands at LOW-MEDIUM position"),
        ("vertical", 0.5, "50% HEIGHT", "Put hands at CENTER height"),
        ("vertical", 0.75, "75% HEIGHT", "Put hands at MEDIUM-HIGH position"),
        ("vertical", 1.0, "MAXIMUM HEIGHT", "Put hands at HIGHEST position"),
    ]
    
    current_step = 0
    countdown_start = None
    countdown_active = False
    capturing = False
    capture_count = 0
    samples_at_point = []
    
    horizontal_samples = []
    vertical_samples = []
    
    SAMPLES_PER_POINT = 30
    COUNTDOWN_DURATION = 5.0
    
    while current_step < len(positions):
        ret, frame = cap.read()
        if not ret:
            break
        
        mode, target_value, title, instruction = positions[current_step]
        
        result = detector.process_frame(frame)
        
        # Draw big step title
        cv2.putText(frame, f"Step {current_step + 1}/10: {title}", 
                   (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)
        cv2.putText(frame, instruction, 
                   (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Target: {target_value:.0%}", 
                   (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        if result['valid']:
            detector.draw_hands(frame, result['hand_landmarks'], result['centers'])
            
            # Show current raw value
            if mode == "horizontal":
                current_raw = result['distance_raw']
                cv2.putText(frame, f"Current Spread: {current_raw:.1f}px", 
                           (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            else:
                current_raw = result['height_raw']
                cv2.putText(frame, f"Current Height: {current_raw:.1f}px", 
                           (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            
            # Start countdown automatically when hands are detected
            if not countdown_active and not capturing:
                countdown_active = True
                countdown_start = time.time()
            
            # Countdown display
            if countdown_active and not capturing:
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
                    print(f"Capturing {title}...")
            
            # Capture samples
            if capturing:
                samples_at_point.append(current_raw)
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
                    # Save median
                    median_raw = np.median(samples_at_point)
                    if mode == "horizontal":
                        horizontal_samples.append((median_raw, target_value))
                        print(f"✓ Horizontal {target_value:.0%}: raw={median_raw:.1f}")
                    else:
                        vertical_samples.append((median_raw, target_value))
                        print(f"✓ Vertical {target_value:.0%}: raw={median_raw:.1f}")
                    
                    # Move to next step
                    capturing = False
                    capture_count = 0
                    countdown_active = False
                    samples_at_point = []
                    current_step += 1
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
        
        # Progress indicator
        progress = f"Progress: {current_step}/10"
        cv2.putText(frame, progress, 
                   (frame.shape[1] - 200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.putText(frame, "Press 'q' to quit", 
                   (20, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        
        cv2.imshow("Linearization Tool", frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\nLinearization cancelled")
            cap.release()
            cv2.destroyAllWindows()
            detector.release()
            return
    
    # All samples collected, compute linearization
    print("\n=== Computing Linearization Functions ===")
    
    # Compute fits for horizontal
    if len(horizontal_samples) >= 2:
        h_linear = compute_linear_fit(horizontal_samples)
        h_poly = compute_polynomial_fit(horizontal_samples, degree=3)
        
        print(f"\nHorizontal:")
        print(f"  Linear: R²={h_linear['r_squared']:.4f}, Mean Error={h_linear['mean_error']:.4f}")
        print(f"  Polynomial: R²={h_poly['r_squared']:.4f}, Mean Error={h_poly['mean_error']:.4f}")
        
        # Choose best (polynomial if significantly better)
        if h_poly['r_squared'] - h_linear['r_squared'] > 0.02:
            calibration['horizontal_linearization'] = h_poly
            print(f"  → Using polynomial (better fit)")
        else:
            calibration['horizontal_linearization'] = h_linear
            print(f"  → Using linear (simpler)")
    
    # Compute fits for vertical
    if len(vertical_samples) >= 2:
        v_linear = compute_linear_fit(vertical_samples)
        v_poly = compute_polynomial_fit(vertical_samples, degree=3)
        
        print(f"\nVertical:")
        print(f"  Linear: R²={v_linear['r_squared']:.4f}, Mean Error={v_linear['mean_error']:.4f}")
        print(f"  Polynomial: R²={v_poly['r_squared']:.4f}, Mean Error={v_poly['mean_error']:.4f}")
        
        # Choose best
        if v_poly['r_squared'] - v_linear['r_squared'] > 0.02:
            calibration['vertical_linearization'] = v_poly
            print(f"  → Using polynomial (better fit)")
        else:
            calibration['vertical_linearization'] = v_linear
            print(f"  → Using linear (simpler)")
    
    # Save updated calibration
    with open(calibration_path, 'w') as f:
        json.dump(calibration, f, indent=4)
    
    print(f"\n✓ Linearization saved to {calibration_path}")
    print("\nLinearization complete! Your tracking is now more accurate.")
    print("Restart tracker.py to use the improved calibration.")
    
    cap.release()
    cv2.destroyAllWindows()
    detector.release()

if __name__ == "__main__":
    main()