from picarx import Picarx
import time

def main():
    px = Picarx()

    try:
        # 1. Move Forward
        print("Moving forward...")
        px.set_dir_servo_angle(0)  # Straight
        px.forward(30)             # Speed 30
        time.sleep(2)              # Move for 2 seconds

        # 2. Turn Left
        print("Turning left...")
        px.set_dir_servo_angle(-30) # Turn steering left (max -30)
        px.forward(30)              # Apply speed again to adjust differential steering
        time.sleep(2)               # Turn for 2 seconds

        # 3. Stop
        print("Stopping...")
        px.stop()
        px.set_dir_servo_angle(0)   # Reset steering

    except KeyboardInterrupt:
        px.stop()

if __name__ == "__main__":
    main()

