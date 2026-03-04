import serial
import time

try:
    # Open COM1
    printer = serial.Serial(
        port='COM1',
        baudrate=9600,   # common default for TM-U220
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=1
    )

    time.sleep(2)  # wait for connection

    # Send text
    printer.write(b"EPSON TM-U220 TEST\n")
    printer.write(b"--------------------------\n")
    printer.write(b"Item 1      10.00\n")
    printer.write(b"Item 2      20.00\n")
    printer.write(b"--------------------------\n")
    printer.write(b"TOTAL       30.00\n\n\n\n\n\n\n\n\n\n\n")

    # Cut paper (ESC/POS cut command)


    printer.write(b'\x1d\x56\x00')
    printer.close()

    print("✅ Serial print sent!")

except Exception as e:
    print("❌ Error:", e)