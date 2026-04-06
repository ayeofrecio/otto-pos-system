import serial
import time

# -----------------------------
# Configuration
# -----------------------------
com_port = 'COM1'     # Your virtual COM port
baud_rate = 9600      # Standard for Epson TM printers

# -----------------------------
# Connect to the printer
# -----------------------------
try:
    printer = serial.Serial(com_port, baud_rate, timeout=1)
except Exception as e:
    print(f"Failed to open COM port {com_port}: {e}")
    exit(1)

# -----------------------------
# ESC/POS Test Receipt
# -----------------------------
receipt = b''

receipt += b'\x1b\x40'                  # Initialize printer
receipt += b'*** TEST RECEIPT ***\n'
receipt += b'Store: My Test Store\n'
receipt += b'Date: 2026-03-26\n'
receipt += b'------------------------\n'
receipt += b'Item 1      $10.00\n'
receipt += b'Item 2      $15.50\n'
receipt += b'Total       $25.50\n'
receipt += b'------------------------\n'
receipt += b'Thank you!\n\n'
receipt += b'\x1d\x56\x41\x10'          # Cut paper command

# -----------------------------
# Send receipt to printer
# -----------------------------
try:
    printer.write(receipt)
    printer.close()
    print("Test receipt sent to COM1")
except Exception as e:
    print(f"Failed to send receipt: {e}")