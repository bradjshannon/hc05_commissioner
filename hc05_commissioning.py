import serial, time
from serial.tools import list_ports

DEBUG = True
COMMON_BAUDS = [9600, 19200, 38400, 57600, 115200]

def list_com_ports():
    ports = list_ports.comports()
    available = []
    print("Available COM ports:")
    for i, port in enumerate(ports):
        details = f"{port.device} - {port.description}"
        if getattr(port, 'manufacturer', None):
            details += f" | Manufacturer: {port.manufacturer}"
        if getattr(port, 'product', None):
            details += f" | Product: {port.product}"
        if getattr(port, 'vid', None) and getattr(port, 'pid', None):
            details += f" | VID:PID = {port.vid:04X}:{port.pid:04X}"
        print(f"{i+1}: {details}")
        available.append(port.device)
    return available

def select_port():
    available = list_com_ports()
    if not available:
        print("No COM ports found. Connect a device and try again.")
        exit(1)
    while True:
        try:
            sel = int(input("Select port number: ").strip())
            if 1 <= sel <= len(available):
                return available[sel-1]
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")

def is_at_mode(ser):
    ser.write("AT\r\n".encode())
    time.sleep(0.5)
    resp = ser.readline().decode().strip()
    return "OK" in resp

def auto_detect_baud(port, debug=DEBUG):
    print("Auto-detecting AT mode baud rate...")
    for baud in COMMON_BAUDS:
        try:
            ser = serial.Serial(port, baud, timeout=1)
            time.sleep(1)
            ser.write("AT\r\n".encode())
            raw = ser.read(ser.in_waiting or 1)
            resp = raw.decode(errors="replace").strip()
            if debug:
                print(f"Baud {baud}: Received {len(raw)} bytes: {raw.hex()} | Decoded: '{resp}'")
            ser.close()
            if "OK" in resp:
                print(f"AT mode detected at {baud} baud.")
                return baud
        except Exception as e:
            if debug:
                print(f"Error at {baud} baud: {e}")
    print("Auto-detection failed.")
    manual = input("Manually enter AT mode baud rate? (Y/n): ").strip().lower() or "y"
    if manual == "y":
        try:
            manual_baud = int(input("Enter baud rate: ").strip())
            ser = serial.Serial(port, manual_baud, timeout=1)
            time.sleep(1)
            ser.write("AT\r\n".encode())
            raw = ser.read(ser.in_waiting or 1)
            resp = raw.decode(errors="replace").strip()
            if debug:
                print(f"Manual baud {manual_baud}: Received {len(raw)} bytes: {raw.hex()} | Decoded: '{resp}'")
            ser.close()
            if "OK" in resp:
                print(f"AT mode confirmed at {manual_baud} baud.")
                return manual_baud
            else:
                print("Manual baud rate did not confirm AT mode.")
        except Exception as e:
            print("Error with manual baud rate:", e)
    return None

def query_current_config(ser):
    config = {}
    ser.write("AT+NAME?\r\n".encode())
    time.sleep(0.5)
    config['name'] = ser.readline().decode().strip() or "Unknown"
    print(f"Current module name: {config['name']}")
    ser.write("AT+ROLE?\r\n".encode())
    time.sleep(0.5)
    config['role'] = ser.readline().decode().strip() or "Unknown"
    print(f"Current role: {config['role']}")
    ser.write("AT+UART?\r\n".encode())
    time.sleep(0.5)
    config['uart'] = ser.readline().decode().strip() or "Unknown"
    print(f"Current UART settings: {config['uart']}")
    return config

def get_new_config():
    print("Enter new configuration settings (press Enter to accept default):")
    default_name = "HC-05"
    default_pswd = "1234"
    default_role = "0"
    default_uart = "9600,0,0"
    cfg = {}
    cfg['name'] = input(f"New module name [{default_name}]: ").strip() or default_name
    cfg['pswd'] = input(f"New AT password [{default_pswd}]: ").strip() or default_pswd
    cfg['role'] = input(f"New role (0=slave, 1=master) [{default_role}]: ").strip() or default_role
    cfg['uart'] = input(f"New UART settings (baud,stop,parity) [{default_uart}]: ").strip() or default_uart
    return cfg

def send_command(ser, cmd):
    ser.write((cmd+"\r\n").encode())
    time.sleep(0.5)
    return ser.readline().decode().strip()

def apply_config(ser, cfg):
    cmds = [
        f"AT+NAME={cfg['name']}",
        f"AT+PSWD={cfg['pswd']}",
        f"AT+ROLE={cfg['role']}",
        f"AT+UART={cfg['uart']}"
    ]
    for cmd in cmds:
        resp = send_command(ser, cmd)
        print(f"Sent: {cmd} | Response: {resp}")
        if "OK" not in resp:
            print("Error applying command:", cmd)
            return False
    return True

def verify_config(ser):
    resp = send_command(ser, "AT+NAME?")
    print("Verification (Name):", resp)

def main():
    last_cfg = None
    while True:
        port = select_port()
        detected_baud = auto_detect_baud(port)
        if detected_baud is None:
            if (input("Failed auto-detection. Retry? (Y/n): ").strip().lower() or "y") == "y":
                continue
            elif (input("Skip module? (Y/n): ").strip().lower() or "y") == "y":
                if (input("Proceed with next module? (Y/n): ").strip().lower() or "y") != "y":
                    break
                else:
                    continue
            else:
                continue

        try:
            ser = serial.Serial(port, detected_baud, timeout=1)
            time.sleep(1)
        except Exception as e:
            print("Connection error:", e)
            if (input("Retry connection? (Y/n): ").strip().lower() or "y") == "y":
                continue
            elif (input("Skip module? (Y/n): ").strip().lower() or "y") == "y":
                if (input("Proceed with next module? (Y/n): ").strip().lower() or "y") != "y":
                    break
                else:
                    continue

        if not is_at_mode(ser):
            print("Module not responding in AT mode.")
            ser.close()
            if (input("Retry module? (Y/n): ").strip().lower() or "y") == "y":
                continue
            elif (input("Skip module? (Y/n): ").strip().lower() or "y") == "y":
                if (input("Proceed with next module? (Y/n): ").strip().lower() or "y") != "y":
                    break
                else:
                    continue

        print("Module connected and in AT mode.")
        print("Querying current configuration:")
        query_current_config(ser)

        if (input("Apply new configuration? (Y/n): ").strip().lower() or "y") == "y":
            if not last_cfg or (input("Reuse last new config? (Y/n): ").strip().lower() or "y") != "y":
                cfg = get_new_config()
            else:
                cfg = last_cfg
                print("Reusing previous configuration settings.")
            last_cfg = cfg

            if (input("Proceed with configuration? (Y/n): ").strip().lower() or "y") != "y":
                ser.close()
                if (input("Skip module? (Y/n): ").strip().lower() or "y") == "y":
                    if (input("Proceed with next module? (Y/n): ").strip().lower() or "y") != "y":
                        break
                    continue
            if not apply_config(ser, cfg):
                print("Configuration failed. Please address the error.")
                ser.close()
                if (input("Retry configuration for this module? (Y/n): ").strip().lower() or "y") == "y":
                    continue
                elif (input("Skip module? (Y/n): ").strip().lower() or "y") == "y":
                    if (input("Proceed with next module? (Y/n): ").strip().lower() or "y") != "y":
                        break
                    continue
            verify_config(ser)
            print("Configuration applied successfully.")
        else:
            print("Leaving module unchanged.")

        ser.close()
        if (input("Proceed with next module? (Y/n): ").strip().lower() or "y") != "y":
            break

if __name__ == "__main__":
    main()
