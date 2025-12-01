import cv2
import mediapipe as mp
import numpy as np

class HandDetector:
    """Pure MediaPipe hand detection - returns raw pixel values only"""
    
    def __init__(self, min_detection_confidence=0.6, min_tracking_confidence=0.6):
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
    
    def get_hand_center_and_size(self, image, hand_landmarks):
        """
        Returns:
          - center of hand (cx, cy) in pixels
          - approximate size (bounding box area) in pixels²
        """
        h, w, _ = image.shape
        xs = [lm.x * w for lm in hand_landmarks.landmark]
        ys = [lm.y * h for lm in hand_landmarks.landmark]

        cx = float(np.mean(xs))
        cy = float(np.mean(ys))

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x
        height = max_y - min_y
        area = width * height

        return cx, cy, area
    
    def process_frame(self, frame):
        """
        Process a frame and return raw hand data.
        
        Returns:
            dict with:
                - valid: bool (True if two hands detected at similar depth)
                - distance_raw: float (pixels between hand centers)
                - height_raw: float (average Y position in pixels)
                - hand_landmarks: list of hand landmarks (for drawing)
                - centers: tuple of ((x1, y1), (x2, y2)) or None
        """
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        output = {
            'valid': False,
            'distance_raw': None,
            'height_raw': None,
            'hand_landmarks': [],
            'centers': None
        }
        
        if results.multi_hand_landmarks and len(results.multi_hand_landmarks) >= 2:
            hand1 = results.multi_hand_landmarks[0]
            hand2 = results.multi_hand_landmarks[1]
            
            x1, y1, s1 = self.get_hand_center_and_size(frame, hand1)
            x2, y2, s2 = self.get_hand_center_and_size(frame, hand2)
            
            # Check if hands are at similar depth (size ratio check)
            if s1 > 0 and s2 > 0:
                size_ratio = s1 / s2 if s1 > s2 else s2 / s1
            else:
                size_ratio = 999.0
            
            # Only valid if hands have comparable size (similar distance from camera)
            if 0.5 <= size_ratio <= 2.0:
                output['valid'] = True
                output['distance_raw'] = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                output['height_raw'] = (y1 + y2) / 2.0
                output['hand_landmarks'] = [hand1, hand2]
                output['centers'] = ((x1, y1), (x2, y2))
        
        return output
    
    def draw_hands(self, frame, hand_landmarks, centers=None):
        """Draw hand landmarks and centers on frame"""
        for hand in hand_landmarks:
            self.mp_drawing.draw_landmarks(
                frame, hand, self.mp_hands.HAND_CONNECTIONS
            )
        
        if centers:
            for (x, y) in centers:
                cv2.circle(frame, (int(x), int(y)), 6, (0, 255, 0), -1)
    
    def release(self):
        """Clean up resources"""
        self.hands.close()