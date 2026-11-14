"""
Asynchronous WebSocket server class with wifi management for MicroPython on
the Raspberry Pi Pico
"""

import json
import time

import network
import uasyncio as asyncio
import ubinascii
import uhashlib
from machine import Pin
from micropython import const

# ==============================================================================
# TYPE CHECKING GUARD (Static Analysis vs Embedded Runtime)
# ==============================================================================
# Standard MicroPython builds do not include the Python 'typing' module,
# importing it directly would cause an ImportError on the device.
# By using TYPE_CHECKING (which is False at runtime but True for tools like
# VS Code/Pylance), we enable static analysis during development while
# keeping the embedded execution clean.
try:
	from typing import TYPE_CHECKING
except ImportError:
	TYPE_CHECKING = False

if TYPE_CHECKING:
	from typing import Any, Callable, Dict, List, Optional


class WebSocketServer:
	CONN_TIMEOUT: int = const(20)
	MAX_CONN_TRIES: int = const(20)

	def __init__(
		self,
		port: int = 8080,
		ssid: str = '',
		password: str = '',
		on_message: Optional[
			Callable[[str, int, asyncio.StreamWriter], Any]
		] = None,
		prt_msg: Optional[Callable[[str], Any]] = None,
	) -> None:
		self.port: int = port
		self.ssid: str = ssid
		self.password: str = password
		self.on_message: (
			Callable[[str, int, asyncio.StreamWriter], Any] | None
		) = on_message
		self.prt_msg: Callable[[str]] | None = prt_msg
		self.clients: List[asyncio.StreamWriter] = []

		self._wlan = network.WLAN(network.STA_IF)
		self._ip: str = ''
		self._led: Pin = Pin('LED', Pin.OUT)  # Using onboard LED
		self._led.value(0)

	async def start(self) -> None:
		"""
		Connects wifi, starts the background monitor, and launches the
		server.
		"""
		connected: bool = False
		tries: int = 0
		while not connected and tries < self.MAX_CONN_TRIES:
			await self._connect_wifi()
		if not connected:
			self._led(0)
			return

		self._led(1)
		# Start the background wifi health watcher
		asyncio.create_task(self._monitor_wifi())

		# Start the TCP server listener
		await asyncio.start_server(
			self._websocket_handler, '0.0.0.0', self.port
		)
		self.print_msg(f'WSS:LISTENING:{self.port}')

		# Keep the server task running continuously in the event loop
		while True:
			await asyncio.sleep(3600)

	############################################################################
	###   WIFI / NETWORKING                                                  ###
	############################################################################
	@property
	def ip(self) -> str:
		"""
		Returns the current local IP address, or None if not connected.
		"""
		return self._ip

	@property
	def wifi_connected(self) -> bool | str:
		return self.ssid and not self._wlan.isconnected()

	async def _connect_wifi(self) -> bool:
		"""
		Handles initial wifi association with a timeout.
		"""
		if not self.ssid:
			self._led(0)  # ensure off
			return True

		# Disable power saving mode so the wifi chip stays fully awake
		# try:
		# 	self._wlan.config(pm=0xA11140)  # Disable wifi sleep for stability
		# except Exception:
		# 	pass

		try:
			# Force clean shutdown of the wireless interface first to clear EPERM states
			self._wlan.active(False)
			await asyncio.sleep(1)

			self._wlan.active(True)
			# Give the CYW43 chip a moment to power up its firmware state
			await asyncio.sleep(0.5)

			self._led(1)
			self.print_msg(f'NET:CONNECTING:{self.ssid}')
			self._wlan.connect(self.ssid, self.password)
		except Exception as e:
			self.print_msg(f'NET:ERR:INIT_EXCEPTION:{e}')
			self._led(0)
			return False

		timeout: int = self.CONN_TIMEOUT
		while not self._wlan.isconnected() and timeout > 0:
			await asyncio.sleep(1)
			timeout -= 1

		if not self._wlan.isconnected():
			self.print_msg('NET:ERR:CONNECTION_TIMEOUT')
			self._led(0)
			return False

		self._ip = self._wlan.ifconfig()[0]
		self._flash_led(3)
		self.print_msg(f'NET:CONNECTED:IP:{self._ip}')
		return True

	async def _monitor_wifi(self) -> None:
		"""
		Background task that monitors wifi health and reconnects if
		dropped.
		"""
		while True:
			await asyncio.sleep(10)
			if self.ssid and not self._wlan.isconnected():
				self.print_msg('NET:ERR:WIFI_DROPPED')
				try:
					self._wlan.connect(self.ssid, self.password)
					timeout: int = self.CONN_TIMEOUT
					while not self._wlan.isconnected() and timeout > 0:
						await asyncio.sleep(1)
						timeout -= 1

					if self._wlan.isconnected():
						self._ip = self._wlan.ifconfig()[0]
						self.print_msg(f'NET:RECONNECTED:IP:{self._ip}')
					else:
						self.print_msg('NET:ERR:RECONNECTION_FAILED')
						self._led(0)
				except Exception as e:
					self.print_msg(f'NET:ERR:RECONNECT_EXCEPTION:{e}')
					self._led(0)

	def _parse_frame(self, data: bytes) -> Optional[str]:
		"""
		Parses, checks opcodes, extracts payload lengths, and unmasks incoming
		client-to-server RFC 6455 WebSocket data frames.

		All client frames are XOR-masked using a 4-byte key for security; this
		function reverses that mask to recover the clean text payload.
		"""
		if len(data) < 2:
			return None

		# Byte 0: Flags and Opcode (Lower 4 bits)
		# Opcode 0x8 signals a connection close frame from the client.
		opcode: int = data[0] & 0x0F
		if opcode == 0x8:
			return 'CLOSE'

		# Byte 1: Mask flag (MSB) and Payload Length (Lower 7 bits)
		masked: bool = (data[1] & 0x80) != 0
		payload_len: int = data[1] & 0x7F

		idx = 2

		# Handle extended payload length framing standards
		if payload_len == 126:
			payload_len = int.from_bytes(data[2:4], 'big')
			idx = 4
		elif payload_len == 127:
			payload_len = int.from_bytes(data[2:10], 'big')
			idx = 10

		# Extract and unmask payload bytes if a masking key is present
		if masked:
			mask_key: bytes = data[idx : idx + 4]
			idx += 4
			encoded_payload: bytes = data[idx : idx + payload_len]
			decoded_bytes = bytes(
				b ^ mask_key[i % 4] for i, b in enumerate(encoded_payload)
			)
			return decoded_bytes.decode('utf-8')
		else:
			return data[idx : idx + payload_len].decode('utf-8')

	async def _websocket_handler(
		self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
	) -> None:
		"""
		Manages individual client socket connections:
		1. Reads incoming HTTP headers and extracts the 'Sec-WebSocket-Key'.
		2. Computes the cryptographic RFC 6455 SHA-1 / Base64 acceptance hash token.
		3. Completes HTTP-to-WebSocket '101 Switching Protocols' upgrade handshake.
		4. Enters an async read loop to parse, unmask, and route incoming commands.
		"""
		addr: Any = writer.get_extra_info('peername')
		self.print_msg(f'WSS:CLIENT:CONNECTION:{addr}')

		try:
			ws_key: Optional[bytes] = None
			while True:
				line: bytes = await reader.readline()
				if not line or line == b'\r\n':
					break
				if line.lower().startswith(b'sec-websocket-key:'):
					ws_key = line.split(b':')[1].strip()

			if not ws_key:
				writer.close()
				return

			sha1 = uhashlib.sha1(
				ws_key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
			)
			accept_key: bytes = ubinascii.b2a_base64(sha1.digest()).strip()

			response: bytes = (
				b'HTTP/1.1 101 Switching Protocols\r\n'
				b'Upgrade: websocket\r\n'
				b'Connection: Upgrade\r\n'
				b'Sec-WebSocket-Accept: ' + accept_key + b'\r\n\r\n'
			)
			await writer.awrite(response)
			self.print_msg('WSS:HANDSHAKE_OK')
			self.clients.append(writer)

			while True:
				try:
					data: bytes = await reader.read(256)
					if not data:
						break

					message: str | None = self._parse_frame(data)
					if message == 'CLOSE':
						try:
							writer.write(bytearray([0x88, 0x00]))
							await writer.drain()
						except Exception:
							pass
						break

					if message and self.on_message:
						await self.on_message(message, 0, writer)
				except Exception:
					break
		except Exception as e:
			self.print_msg(f'WSS:ERR:{e}')
		finally:
			if writer in self.clients:
				self.clients.remove(writer)
			try:
				writer.close()
				await writer.wait_closed()
			except Exception:
				pass
			self.print_msg('WSS:CLIENT_DISCONNECTED')

	############################################################################
	###   MESSAGING                                                          ###
	############################################################################

	async def broadcast(self, message: Dict[str, Any] | str) -> None:
		"""
		Broadcasts a JSON dictionary or string to all active clients.
		"""
		msg_str: str = (
			json.dumps(message) if isinstance(message, dict) else message
		)
		disconnected: list[Any] = []
		for client_writer in self.clients:
			try:
				await self.send(client_writer, msg_str)
			except Exception:
				disconnected.append(client_writer)

		for dead_client in disconnected:
			if dead_client in self.clients:
				self.clients.remove(dead_client)

	def print_msg(self, msg: str) -> None:
		if self.prt_msg:
			self.prt_msg(msg)

	async def send(self, writer: asyncio.StreamWriter, message: str) -> None:
		"""
		Constructs and sends an unmasked RFC 6455 text frame.
		"""
		payload: bytes = message.encode('utf-8')
		length: int = len(payload)
		# Header byte 0: 0x81 (FIN bit set + Text opcode)
		header = bytearray([0x81])

		# Header byte(s) 1+: Payload length encoding rules
		if length <= 125:
			header.append(length)
		elif length <= 65535:
			header.append(126)
			header.extend(length.to_bytes(2, 'big'))
		else:
			header.append(127)
			header.extend(length.to_bytes(8, 'big'))

		writer.write(header + payload)
		await writer.drain()

	############################################################################
	###   HELPER FUNCTIONS etc                                               ###
	############################################################################

	def _flash_led(
		self, times: int, delay: int = 250, end_state: int = 0
	) -> None:
		if self._led:
			for _ in range(times):
				self._led(1)
				time.sleep_ms(delay)
				self._led(0)
				time.sleep_ms(delay)
			self._led(end_state)
