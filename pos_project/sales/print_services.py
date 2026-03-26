import socket
import serial
import win32print


class ReceiptPrinter:
    def __init__(self, port_config):
        self.port_config = port_config
        self.conn = None

    def connect(self):
        t = self.port_config.connection_type

        if t == "SERIAL":
            self.conn = serial.Serial(
                port=self.port_config.port_name,
                baudrate=self.port_config.baudrate or 9600,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1
            )

        elif t == "NETWORK":
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((
                self.port_config.ip_address,
                int(self.port_config.port_no or 9100)
            ))

        elif t == "WINDOWS":
            name = self.port_config.printer_name or win32print.GetDefaultPrinter()
            self.conn = win32print.OpenPrinter(name)

        else:
            raise Exception("Unsupported printer type")

    def write(self, data: bytes):
        t = self.port_config.connection_type

        if t == "SERIAL":
            self.conn.write(data)

        elif t == "NETWORK":
            self.conn.sendall(data)

        elif t == "WINDOWS":
            win32print.StartDocPrinter(self.conn, 1, ("Receipt", None, "RAW"))
            win32print.StartPagePrinter(self.conn)
            win32print.WritePrinter(self.conn, data)
            win32print.EndPagePrinter(self.conn)
            win32print.EndDocPrinter(self.conn)

    def close(self):
        try:
            if self.port_config.connection_type in ["SERIAL", "NETWORK"]:
                self.conn.close()
            elif self.port_config.connection_type == "WINDOWS":
                win32print.ClosePrinter(self.conn)
        except:
            pass