# Pet Follower Project

This project implements a pet follower behavior on the SunFounder Picar-X robot using a Raspberry Pi.

## Setup

Follow the [SETUP_GUIDE.md](SETUP_GUIDE.md) to install dependencies and the Picar-X library.

## Running the API Server

The main entry point is the web API server, which provides a dashboard for controlling the robot and viewing the camera feed.

### 1. Start the Server

Run the following command from the project root:

```bash
python3 -m pet_follower.web.api_server
```

By default, the server listens on port **8000**. You can specify a different host or port:

```bash
python3 -m pet_follower.web.api_server --host 0.0.0.0 --port 8080
```

### 2. Access the Dashboard

Open your web browser and navigate to:

```
http://<raspberry-pi-ip>:8000/dashboard.html
```

(Replace `<raspberry-pi-ip>` with the IP address of your Raspberry Pi)

## Functionality

The system provides the following features:

- **Live Video Feed:** Streams video from the robot's camera to the web dashboard.
- **Object Detection:** Uses YOLO (via `ultralytics`) to detect dogs (or other pets) in the video feed.
- **Motion Control:**
  - **Follow Mode:** Automatically tracks and follows the detected pet, maintaining a safe distance.
  - **Manual Drive:** Allows manual control of the robot via the dashboard (forward, backward, turn).
- **Interaction:** Performs celebratory movements (spin, bounce) and plays sounds.
- **Safety:** Includes obstacle avoidance using ultrasonic sensors and cliff detection (if enabled) using grayscale sensors.
- **Cloud Integration:** Uploads snapshots and video clips to a cloud server and fetches daily logs/emotion insights (configured via `GCP_SERVER_URL` in `api_server.py`).

