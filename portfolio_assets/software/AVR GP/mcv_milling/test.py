import libusb_package
import usb.core
import can
import time

# Fix libusb
be = libusb_package.get_libusb1_backend()
_orig = usb.core.find
def patched(*args, **kwargs):
    kwargs.setdefault('backend', be)
    return _orig(*args, **kwargs)
usb.core.find = patched

network = canopen.Network()
network.connect(interface='gs_usb', channel=0, bitrate=500000)
print("CAN connected")

# Scan
network.scanner.search()
time.sleep(0.5)
print("Nodes found:", network.scanner.nodes)
# Should now print: {3}

# Add node with correct ID = 3
node = network.add_node(3, 'SELXM28_015034E.eds')

# Read status
status = node.sdo['Statusword'].raw
print(f"Status word: 0x{status:04X}")

network.disconnect()
print("Done")
