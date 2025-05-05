# shift_listener.py
import keyboard
import time
import subprocess
import sys
import os

# --- Configuration ---
# Time window (in seconds) within which the second Shift press must occur
DOUBLE_PRESS_INTERVAL = 0.3 # Adjust as needed

# LAUNCHER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__),"slick_launcher" '__main__.py'))
LAUNCHER_MOD = "slick_launcher"

# --- Listener Logic ---
last_shift_press_time = 0
shift_pressed = False

def on_key_event(event):
    """Callback function for keyboard events."""
    global last_shift_press_time
    global shift_pressed

    if event.name in ['shift', 'right shift']:
        if event.event_type == keyboard.KEY_DOWN:
            # Only consider a new press if the key is not already pressed
            if not shift_pressed:
                shift_pressed = True
                current_time = time.time()
                time_diff = current_time - last_shift_press_time

                # Check if the second press happened within the interval
                if time_diff < DOUBLE_PRESS_INTERVAL and time_diff > 0:  # time_diff > 0 prevents triggering on initial press
                    print("Double Shift detected! Launching Slick Launcher...")
                    launch_slick_launcher()
                    last_shift_press_time = 0  # Reset to avoid triple/quadruple triggers
                else:
                    # This is the first press (or too slow)
                    last_shift_press_time = current_time

        elif event.event_type == keyboard.KEY_UP:
            # Reset the flag when the key is released
            shift_pressed = False

def launch_slick_launcher():
    """Launches the Slick Launcher application."""
    try:
        # Use sys.executable to launch the script with the same Python interpreter
        subprocess.Popen([sys.executable,"-m", LAUNCHER_MOD])
        print(f"Started process: {sys.executable} {LAUNCHER_MOD}")
    except Exception as e:
        print(f"Failed to launch {LAUNCHER_MOD}: {e}", file=sys.stderr)

# --- Main Execution ---
if __name__ == "__main__":
    print(f"Shift listener started. Press Shift twice quickly to launch {os.path.basename(LAUNCHER_MOD)}.")
    print(f"Monitoring for double Shift press within {DOUBLE_PRESS_INTERVAL} seconds.")
    print("Press Ctrl+C to stop the listener.")

    try:
        # Hook all keyboard events and pass them to our callback
        keyboard.hook(on_key_event)
        # Keep the script running indefinitely, waiting for events
        keyboard.wait() # This blocks until a hotkey is pressed, but works here to keep the hook active

    except KeyboardInterrupt:
        print("\nListener stopped.")
    except Exception as e:
         print(f"An error occurred in the listener: {e}", file=sys.stderr)
