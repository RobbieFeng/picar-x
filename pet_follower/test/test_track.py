import time
from pet_follower.motion import MotionController
from pet_follower.vision import DetectionResult

def main():
    print("Initializing MotionController...")
    motion = MotionController()
    
    print("Starting fake tracking loop... (Press Ctrl+C to stop)")
    print("Phase 1: Steering RIGHT (for 5 seconds)")
    
    start_time = time.monotonic()
    phase_switched = False
    
    try:
        while True:
            elapsed = time.monotonic() - start_time
            
            if elapsed < 5.0:
                # Target to the right (center > 320) -> Should steer right
                center_x = 500.0
            else:
                if not phase_switched:
                    print("Phase 2: Steering LEFT")
                    phase_switched = True
                # Target to the left (center < 320) -> Should steer left
                center_x = 140.0

            det = DetectionResult(
                center=(center_x, 240.0),
                bbox=(center_x - 20, 200.0, center_x + 20, 280.0),
                confidence=0.9,
                frame_size=(480, 640),
                approx_distance_cm=50.0
            )
            
            motion.track_target(det)
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping robot...")
        motion.stop()
        print("Done.")

if __name__ == "__main__":
    main()
