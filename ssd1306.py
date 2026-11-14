from machine import I2C
from micropython import const

# Constants
DISP_WIDTH: int = const(128)
DISP_HEIGHT: int = const(64)
LINE_HEIGHT: int = const(8)
NUM_LINES: int = const(8)
CHAR_WIDTH: int = const(5)
CHAR_HEIGHT: int = const(7)

FONT_NORMAL: int = const(1)
FONT_DOUBLE: int = const(2)

# 5x7 ASCII font lookup table (character codes 0x20 - 0x7E)
FONT_5X7: list[bytes] = [
	b'\x00\x00\x00\x00\x00',
	b'\x00\x00\x5f\x00\x00',
	b'\x00\x07\x00\x07\x00',
	b'\x14\x7f\x14\x7f\x14',
	b'\x24\x2a\x7f\x2a\x12',
	b'\x23\x13\x08\x64\x62',
	b'\x36\x49\x55\x22\x50',
	b'\x00\x05\x03\x00\x00',
	b'\x00\x1c\x22\x41\x00',
	b'\x00\x41\x22\x1c\x00',
	b'\x14\x08\x3e\x08\x14',
	b'\x08\x08\x3e\x08\x08',
	b'\x00\x50\x30\x00\x00',
	b'\x08\x08\x08\x08\x08',
	b'\x00\x60\x60\x00\x00',
	b'\x20\x10\x08\x04\x02',
	b'\x3e\x51\x49\x45\x3e',
	b'\x00\x42\x7f\x40\x00',
	b'\x42\x61\x51\x49\x46',
	b'\x21\x41\x45\x4b\x31',
	b'\x18\x14\x12\x7f\x10',
	b'\x27\x45\x45\x45\x39',
	b'\x3c\x4a\x49\x49\x30',
	b'\x01\x71\x09\x05\x03',
	b'\x36\x49\x49\x49\x36',
	b'\x06\x49\x49\x29\x1e',
	b'\x00\x36\x36\x00\x00',
	b'\x00\x56\x36\x00\x00',
	b'\x08\x14\x22\x41\x00',
	b'\x14\x14\x14\x14\x14',
	b'\x00\x41\x22\x14\x08',
	b'\x02\x01\x51\x09\x06',
	b'\x32\x49\x79\x41\x3e',
	b'\x7e\x11\x11\x11\x7e',
	b'\x7f\x49\x49\x49\x36',
	b'\x3e\x41\x41\x41\x22',
	b'\x7f\x41\x41\x22\x1c',
	b'\x7f\x49\x49\x49\x41',
	b'\x7f\x09\x09\x09\x01',
	b'\x3e\x41\x49\x49\x7a',
	b'\x7f\x08\x08\x08\x7f',
	b'\x00\x41\x7f\x41\x00',
	b'\x20\x40\x41\x3f\x01',
	b'\x7f\x08\x14\x22\x41',
	b'\x7f\x40\x40\x40\x40',
	b'\x7f\x02\x0c\x02\x7f',
	b'\x7f\x04\x08\x10\x7f',
	b'\x3e\x41\x41\x41\x3e',
	b'\x7f\x09\x09\x09\x06',
	b'\x3e\x41\x51\x21\x5e',
	b'\x7f\x09\x19\x29\x46',
	b'\x26\x49\x49\x49\x32',
	b'\x01\x01\x7f\x01\x01',
	b'\x3f\x40\x40\x40\x3f',
	b'\x1f\x20\x40\x20\x1f',
	b'\x3f\x40\x38\x40\x3f',
	b'\x63\x14\x08\x14\x63',
	b'\x07\x08\x70\x08\x07',
	b'\x61\x51\x49\x45\x43',
	b'\x00\x7f\x41\x41\x00',
	b'\x02\x04\x08\x10\x20',
	b'\x00\x41\x41\x7f\x00',
	b'\x04\x02\x01\x02\x04',
	b'\x40\x40\x40\x40\x40',
	b'\x00\x01\x02\x04\x00',
	b'\x20\x54\x54\x54\x78',
	b'\x7f\x48\x44\x44\x38',
	b'\x38\x44\x44\x44\x20',
	b'\x38\x44\x44\x48\x7f',
	b'\x38\x54\x54\x54\x18',
	b'\x08\x7e\x09\x01\x02',
	b'\x0c\x52\x52\x52\x3e',
	b'\x7f\x08\x04\x04\x78',
	b'\x00\x44\x7d\x40\x00',
	b'\x20\x40\x44\x3d\x00',
	b'\x7f\x10\x28\x44\x00',
	b'\x00\x41\x7f\x40\x00',
	b'\x7c\x04\x18\x04\x78',
	b'\x7c\x08\x04\x04\x78',
	b'\x38\x44\x44\x44\x38',
	b'\x7c\x14\x14\x14\x08',
	b'\x08\x14\x14\x18\x7c',
	b'\x7c\x08\x04\x04\x08',
	b'\x48\x54\x54\x54\x20',
	b'\x04\x3e\x44\x24\x08',
	b'\x3c\x40\x40\x20\x7c',
	b'\x1c\x20\x40\x20\x1c',
	b'\x3c\x40\x30\x40\x3c',
	b'\x44\x28\x10\x28\x44',
	b'\x0c\x50\x50\x50\x3c',
	b'\x44\x64\x54\x4c\x44',
	b'\x08\x36\x41\x41\x00',
	b'\x00\x00\x7f\x00\x00',
	b'\x00\x41\x41\x36\x08',
	b'\x08\x08\x2a\x1c\x08',
]


class SSD1306:
	def __init__(self, i2c: I2C, addr: int) -> None:
		self.i2c: I2C = i2c
		self.addr: int = addr
		self.buffer = bytearray(1024)
		self.init_display()

	def cmd(self, cmd_byte: int) -> None:
		"""
		Send a command to the display by prefixing the byte with a null byte,
		telling the display that this is a command.
		"""
		self.i2c.writeto(self.addr, b'\x00' + bytes([cmd_byte]))

	def init_display(self) -> None:
		cmds: list[int] = [
			0xAE,  # Display OFF
			0x20,
			0x00,  # Set Memory Addressing Mode to Horizontal Addressing Mode
			0xB0,  # Set Page Start Address for Page Addressing Mode to 0
			0xC8,  # Set COM Output Scan Direction (remapped mode)
			0x00,  # Set low column address
			0x10,  # Set high column address
			0x40,  # Set start line address
			0x81,
			0x7F,  # Set contrast control register to mid-scale
			0xA1,  # Set segment re-map
			0xA6,  # Set normal display mode
			0xA8,
			0x3F,  # Set multiplex ratio to 1/64 duty
			0xD3,
			0x00,  # Set display offset to 0
			0xD5,
			0x80,  # Set display clock divide ratio/oscillator frequency
			0xD9,
			0xF1,  # Set pre-charge period
			0xDA,
			0x12,  # Set COM pins hardware configuration
			0xDB,
			0x40,  # Set VCOMH deselect level
			0x8D,
			0x14,  # Enable charge pump regulator
			0xAF,  # Display ON
		]
		for c in cmds:
			self.cmd(c)
		self.clear()

	def clear(self) -> None:
		"""
		Zero-out the pixel buffer.
		"""
		for i in range(len(self.buffer)):
			self.buffer[i] = 0

	def clearln(self, line: int) -> None:
		"""
		Clear out one line's worth of the buffer.
		"""
		if line < 0 or line >= NUM_LINES:
			return
		start_idx: int = line * DISP_WIDTH
		for i in range(start_idx, start_idx + DISP_WIDTH):
			self.buffer[i] = 0

	def draw_pixel(self, x: int, y: int, turn_on: bool) -> None:
		if x < 0 or x >= DISP_WIDTH or y < 0 or y >= DISP_HEIGHT:
			return

		page: int = y // LINE_HEIGHT
		bit: int = y % LINE_HEIGHT
		index: int = page * DISP_WIDTH + x

		if turn_on:
			self.buffer[index] |= 1 << bit
		else:
			self.buffer[index] &= ~(1 << bit)

	def printstr_scaled(
		self, x: int, y: int, text: str, scale: int = FONT_NORMAL
	) -> None:
		if scale < FONT_NORMAL:
			scale = FONT_NORMAL
		if scale > FONT_DOUBLE:
			scale = FONT_DOUBLE

		for char in text:
			code: int = ord(char)
			if code < 0x20 or code > 0x7E:
				code = ord('?')

			idx: int = code - 0x20
			glyph: bytes = FONT_5X7[idx]

			for col in range(CHAR_WIDTH):
				line_val: int = glyph[col]
				for bit in range(CHAR_HEIGHT):
					pixel_active: bool = (line_val & (1 << bit)) != 0
					for sx in range(scale):
						for sy in range(scale):
							self.draw_pixel(
								x + (col * scale) + sx,
								y + (bit * scale) + sy,
								pixel_active,
							)
			x += (CHAR_WIDTH + 1) * scale

	def printstr(self, x: int, y: int, text: str) -> None:
		self.printstr_scaled(x, y, text, FONT_NORMAL)

	def printstr_double(self, x: int, y: int, text: str) -> None:
		self.printstr_scaled(x, y, text, FONT_DOUBLE)

	def println(self, line: int, text: str) -> None:
		self.clearln(line)
		y: int = line * LINE_HEIGHT
		self.printstr_scaled(0, y, text, FONT_NORMAL)

	def show(self) -> None:
		self.cmd(0x21)  # Set column address range
		self.cmd(0)
		self.cmd(127)

		self.cmd(0x22)  # Set page address range
		self.cmd(0)
		self.cmd(7)

		# Transmit data stream prefix byte (0x40) followed by 1024 frame buffer
		# bytes
		payload = bytearray(1025)
		payload[0] = 0x40
		payload[1:] = self.buffer
		self.i2c.writeto(self.addr, payload)
