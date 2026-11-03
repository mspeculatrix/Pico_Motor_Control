from machine import I2C, Pin

from ssd1306 import SSD1306

# Initialize I2C0 on standard pins (GPIO 8 for SDA, GPIO 9 for SCL)
# or whichever pins your hardware uses
i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400000)

# Create display instance
display = SSD1306(i2c)

# Write text line-by-line
display.println(0, 'Pico 2 MicroPython')
display.println(1, 'SSD1306 Ready!')

# Draw scaled text anywhere on screen
display.printstr_double(0, 24, 'Hello!')

# Push buffer to physical display
display.show()
