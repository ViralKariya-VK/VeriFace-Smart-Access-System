import serial
import threading

class Arduino:
    _instance = None

    def __new__(cls, port="COM7", baudrate=9600, timeout=1):
        if cls._instance is None:
            cls._instance = super(Arduino, cls).__new__(cls)
            try:
                cls._instance.serial = serial.Serial(port, baudrate, timeout=timeout)
                print(f"✅ Connected to Arduino on {port}")
            except serial.SerialException as e:
                print(f"❌ ERROR: Could not connect to Arduino: {e}")
                cls._instance.serial = None  # Avoid crashes if not connected
        return cls._instance

    def send_command(self, command):
        """Send a command to the Arduino and read the response."""
        if self.serial and self.serial.is_open:
            self.serial.write(f"{command}\n".encode())
            print(f"📤 Sent: {command}")
            response = self.serial.readline().decode().strip()
            print(f"📥 Received: {response}")
            return response
        else:
            print("❌ ERROR: Arduino is not connected!")
            return None

    def close(self):
        """Close the serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("🔌 Arduino connection closed.")

    def read_response(self):
        """Read response from Arduino (non-blocking)."""
        if self.serial and self.serial.in_waiting > 0:
            return self.serial.readline().decode().strip()
        return None
    
    def get_status(self):
        if self.serial and self.serial.is_open:
            self.serial.reset_input_buffer()
            self.serial.write(b"STATUS\n")
            status = self.serial.readline().decode().strip()
            print(f"📥 Status: {status}")
            return status.lower()  # returns 'on' or 'off'
        return "unknown"

# Singleton instance
arduino_instance = Arduino()
