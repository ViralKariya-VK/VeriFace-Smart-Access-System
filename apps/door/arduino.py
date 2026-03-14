import threading
import time
from django.conf import settings


class DoorController:
    # Singleton — same reason as CameraManager
    # Only one serial connection to Arduino should ever exist
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Simulation state — tracks door state when Arduino isn't connected
        # This is what gets printed to terminal during development
        self._simulated_state = 'off'  # 'on' = open, 'off' = closed
        self.serial = None
        self._connect()

    def _connect(self):
        """Try to connect to Arduino. Fall back to simulation if not available."""
        port = settings.ARDUINO_PORT
        baudrate = settings.ARDUINO_BAUDRATE

        try:
            import serial
            self.serial = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Arduino resets on serial connect — wait for it to boot
            print(f"Arduino connected on {port}")
        except Exception as e:
            # This is expected during development without hardware
            # In production, you'd want to alert here
            print(f"Arduino not found on {port} — running in simulation mode")
            print(f"   Door commands will be printed to terminal instead")
            self.serial = None

    @property
    def is_simulation(self):
        return self.serial is None or not self.serial.is_open

    def send_command(self, command):
        """
        Send OPEN or CLOSE to Arduino.
        Falls back to terminal simulation if hardware not connected.

        Why uppercase commands?
        Arduino sketch uses equalsIgnoreCase() so both work,
        but uppercase is the canonical form we define here.
        """
        command = command.upper()

        if self.is_simulation:
            # Simulation mode — just track state and print
            if command == 'OPEN':
                self._simulated_state = 'on'
                print("[SIMULATION] Door OPENED")
            elif command == 'CLOSE':
                self._simulated_state = 'off'
                print("[SIMULATION] Door CLOSED")
            return f"SIMULATED_{command}"

        # Real Arduino path
        try:
            self.serial.reset_input_buffer()  # Clear any stale responses
            self.serial.write(f"{command}\n".encode())
            response = self.serial.readline().decode().strip()
            print(f"Sent: {command} | Response: {response}")
            return response
        except Exception as e:
            print(f"Arduino command failed: {e}")
            return None

    def get_status(self):
        """
        Returns 'on' (door open) or 'off' (door closed).

        Why not just track state in memory always?
        Because Arduino is the source of truth — someone could
        manually trigger the relay. We ask Arduino directly.
        In simulation we return our tracked state.
        """
        if self.is_simulation:
            status = self._simulated_state
            print(f"[SIMULATION] Door status: {status}")
            return status

        try:
            self.serial.reset_input_buffer()
            self.serial.write(b"STATUS\n")
            response = self.serial.readline().decode().strip().lower()
            # Arduino returns 'ON' or 'OFF' — we lowercase for consistency
            return response if response in ('on', 'off') else 'unknown'
        except Exception as e:
            print(f"Status check failed: {e}")
            return 'unknown'

    def open_door(self):
        """Convenience method — open door then auto-close after 5 seconds"""
        self.send_command('OPEN')
        # Auto-close in background thread so we don't block the caller
        # Alternative: Celery task — but that's overkill for a 5-second delay
        thread = threading.Thread(target=self._auto_close, daemon=True)
        thread.start()

    def _auto_close(self):
        time.sleep(5)
        self.send_command('CLOSE')
        print("Door auto-closed after 5 seconds")

    def close(self):
        """Clean shutdown — called when server stops"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Arduino connection closed")


# Singleton instance — imported everywhere
door_controller = DoorController()