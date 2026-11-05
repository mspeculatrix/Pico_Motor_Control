"""
Pico 2W Asynchronous Robot Motor Control Hub for the Raspberry Pi Pico 2W.

Runs a WebSocket server for remote communication.
"""

import json
import sys

import uasyncio as asyncio
import uselect

# ADC needed only if using analogue sensors.
# I2C needed only if using OLED panel or other I2C device.
from machine import I2C, UART, Pin

from config import Config
from L298_motor_controller import Direction, L298MotorController, Speed
from sensors import Sensors
from ssd1306 import SSD1306  # Needed only if using I2C OLED panel

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
	from typing import Any, Optional

from ws_server import WebSocketServer

# ==============================================================================
# GLOBALS
# ==============================================================================

MOTORCTRL = L298MotorController(
	Config.MOTOR_L_PWM,
	Config.MOTOR_L_IN1,
	Config.MOTOR_L_IN2,
	Config.MOTOR_R_PWM,
	Config.MOTOR_R_IN3,
	Config.MOTOR_R_IN4,
)

# Initialize WebSocket server with credentials, callback and port
ws_svr = WebSocketServer(
	port=8080, ssid=Config.WIFI_SSID, password=Config.WIFI_PASS
)

# Initialize messaging UART
comm_port: UART = UART(
	Config.UART_PORT,
	baudrate=Config.UART_BAUD,
	tx=Config.UART_TX,
	rx=Config.UART_RX,
)


# ==============================================================================
# INTERRUPT SERVICE ROUTINE FOR DIGITAL SENSORS
# ==============================================================================
def sensor_isr(pin: Pin) -> None:
	"""
	This function is needed only if using digital sensors with interrupts.
	This function must be kept extremely lightweight.
	"""
	global sensors
	if pin == sensors.ds0:
		sensors.add_trigger_flag(sensors.LEFT_TRIGGERED)
	elif pin == sensors.ds1:
		sensors.add_trigger_flag(sensors.RIGHT_TRIGGERED)

	# Immediate safety stop at the hardware/interrupt level
	MOTORCTRL.stop()


# Sensor registers & state --- needed only if using sensors --------------------
sensors: Sensors = Sensors(
	Config.PROX_SENSOR_L,
	Config.PROX_SENSOR_R,
	Config.ADC0,
	Config.ADC1,
	Config.ADC2,
	sensor_isr,
)
# ----- end of sensor-related block  -------------------------------------------

# ----- If using an OLED display on I2C0 ---------------------------------------
oled_i2c = I2C(
	Config.OLED_I2C_PORT,
	scl=Config.OLED_I2C_SCL,
	sda=Config.OLED_I2C_SDA,
	freq=Config.OLED_I2C_FREQ,
)
# Create display instance
display: SSD1306 = SSD1306(oled_i2c, Config.SSD1306_I2C_ADDR)
# ----- end of OLED block ------------------------------------------------------


# ==============================================================================
# ASYNCHRONOUS TASK: PERFORM ACTIONS IN RESPONSE TO SENSOR INPUT
# ==============================================================================
async def execute_action(
	left: bool = False, right: bool = False, analogue_trigger: bool = False
) -> None:
	"""
	Repertoire of asynchronous actions using non-blocking sleeps. This is
	primarily for use with sensors.

	These are just sample actions. Change them to suit how you want your robot
	to respond. This is where you'll have the most fun coming up with suitable
	logic.
	"""
	print(f'[ACTION] L={left}, R={right}, ADC={analogue_trigger}')

	# Example decision tree
	if left and right:
		# Both triggered: Head-on collision risk -> Backup straight, turn hard right
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.SP_SLOW)
		await asyncio.sleep_ms(2000)  # Reverse for 2 seconds

		MOTORCTRL.set_direction(Direction.ROTATE_R)
		MOTORCTRL.set_speed(Speed.SP_NORMAL)
		await asyncio.sleep_ms(1000)  # Turn right for 1 second

	elif left:
		# Only left triggered -> Obstacle on left, veer/turn right
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.SP_CRAWL)
		await asyncio.sleep_ms(1000)

		MOTORCTRL.set_direction(Direction.ROTATE_R)
		MOTORCTRL.set_speed(Speed.SP_SLOW)
		await asyncio.sleep_ms(800)

	elif right:
		# Only right triggered -> Obstacle on right, veer/turn left
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.SP_CRAWL)
		await asyncio.sleep_ms(1000)

		MOTORCTRL.set_direction(Direction.ROTATE_L)
		MOTORCTRL.set_speed(Speed.SP_SLOW)
		await asyncio.sleep_ms(800)

	elif analogue_trigger:
		# Analogue sensor close proximity warning - slowly reverse for 1.5s
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.SP_SLOW)
		await asyncio.sleep_ms(1500)

	# Bring motors to a controlled stop after manoeuvre
	MOTORCTRL.stop()
	print('[ACTION] Manoeuvre complete.')


# ==============================================================================
# SEND MESSAGE VIA comm_port
# ==============================================================================
def send_uart_msg(msg: str) -> None:
	"""
	Send a plain text message or telemetry data specifically to comm_port.
	"""
	comm_port.write((msg + '\n').encode('utf-8'))


# ==============================================================================
# ASYNCHRONOUS TASK: SENSOR MONITORING
# ==============================================================================
async def sensor_supervisor_task() -> None:
	"""
	Runs concurrently in the event loop. Monitors digital sensor flags (as set
	by the ISR) and analogue sensors, triggering non-blocking actions.
	"""
	global sensors

	print('[SYSTEM] Sensor monitoring active.')
	while True:
		await sensors.action_done.wait()  # instant response if action_done set
		# Check digital sensors via the flag register
		triggered: int = sensors.read_and_clear_flag_register()
		if triggered:  # has a non-zero value
			sensors.action_done.clear()
			try:
				# Analyze which sensor(s) fired
				left = bool(triggered & sensors.LEFT_TRIGGERED)
				right = bool(triggered & sensors.RIGHT_TRIGGERED)
				await execute_action(left=left, right=right)
			finally:
				# reset 'idle' state even if an exception occurs
				sensors.action_done.set()

		# Poll analogue sensors
		# Example threshold logic: ADC value below safe limit
		if sensors.is_analogue_triggered(0):
			sensors.action_done.clear()
			try:
				await execute_action(analogue_trigger=True)
			finally:
				sensors.action_done.set()

		await asyncio.sleep_ms(50)  # Check 20 times per second


# ==============================================================================
# CORE COMMAND ROUTERS
# ==============================================================================
async def handle_incoming_message(
	cmd_str: str, source: int = 0, writer: Optional[asyncio.StreamWriter] = None
) -> None:
	"""
	Callback passed into WebSocketServer to process incoming messages.
	For each command, the response will be a dict with mandatory key of
	'type', 'cmd' (which just echoes back the command received) and 'result'.
	There may be other keys depending on the command.
	"""
	global MOTORCTRL
	response: dict[str, str | int] = {
		'type': 'none',
		'cmd': cmd_str,
		'result': 'none',
	}
	cmd_str = cmd_str.strip()

	# Movement commands
	if cmd_str == 'STOP':
		await sensors.action_done.wait()
		MOTORCTRL.stop()
		response['type'] = 'motor'
		response['result'] = 'stop'
	elif cmd_str == 'PARK':
		await sensors.action_done.wait()
		MOTORCTRL.park()
		response['type'] = 'motor'
		response['result'] = 'park'
	elif hasattr(Direction, cmd_str):
		await sensors.action_done.wait()
		MOTORCTRL.set_direction(getattr(Direction, cmd_str))
		response['type'] = 'motor'
		response['result'] = 'direction'
	elif hasattr(Speed, cmd_str):
		await sensors.action_done.wait()
		MOTORCTRL.set_speed(getattr(Speed, cmd_str))
		response['type'] = 'motor'
		response['result'] = 'speed'

	# Other commands
	elif cmd_str == 'STATUS':
		response['type'] = 'STATE'
		response['clients'] = len(ws_svr.clients)
	elif cmd_str == 'IP':
		response['type'] = 'STATE'
		response['result'] = f'{ws_svr.ip}'
	else:
		response['type'] = 'ERROR'
		response['result'] = 'Unknown command'

	if source in (Config.MSG_SRC_CLI, Config.MSG_SRC_UART):
		for key in response:
			msg: str = f'[{key}] {response[key]}'
			print(msg)  # to USB CLI
			send_uart_msg(msg)  # to UART CLI
	elif source == Config.MSG_SRC_WS:
		if writer is not None:  # respond to specific WS client
			await ws_svr.send(writer, json.dumps(response))
		else:
			await ws_svr.broadcast(response)


# ==============================================================================
# ASYNCHRONOUS TASK: NON-BLOCKING USB-SERIAL CLI
# ==============================================================================
async def cli_task() -> None:
	"""
	Asynchronous task managing local interactive input over USB CDC Serial.

	Uses `uselect.poll()` to inspect `sys.stdin` non-blockingly. This prevents
	the REPL input reader from freezing the entire system event loop when
	the user isn't typing.

	Incoming bytes are stored in a buffer until a carriage return or newline is
	encountered, at which point the process_command() function is invoked and
	the buffer reset.
	"""
	poll_obj = uselect.poll()
	poll_obj.register(sys.stdin, uselect.POLLIN)
	buffer: str = ''
	print('[CLI] USB Serial CLI ready.')

	while True:
		# Check input stream with zero timeout (non-blocking poll)
		if poll_obj.poll(0):
			char: str | Any = sys.stdin.read(1)
			if char:
				# Handle line termination (Enter key)
				if char == '\n' or char == '\r':
					if buffer:
						sys.stdout.write('\n')
						await handle_incoming_message(
							buffer, Config.MSG_SRC_CLI
						)
						buffer = ''
				# Handle backspace key code (ASCII 127)
				elif ord(char) == 127:
					if len(buffer) > 0:
						buffer = buffer[:-1]
						sys.stdout.write('\b \b')  # Visual terminal backspace
				else:
					sys.stdout.write(char)  # Local character echo
					buffer += char
		# Yield execution back to the uasyncio event loop for 20ms
		await asyncio.sleep_ms(20)


async def uart_cli_task() -> None:
	"""
	Asynchronous task managing serial input from comm_port (GP0/GP1).
	Feeds commands into the shared handle_incoming_message pipeline.
	"""
	buffer: str = ''
	print('[comm_port] Hardware serial CLI ready on GP0/GP1.')

	while True:
		# Check if bytes are waiting in the hardware FIFO buffer
		if comm_port.any():
			data: bytes | None = comm_port.read(comm_port.any())
			if data:
				try:
					text = data.decode('utf-8')
				except UnicodeError:
					text: str = ''

				for char in text:
					# Handle line termination (Enter key / newline)
					if char == '\n' or char == '\r':
						if buffer:
							# Process command, routing response back to comm_port
							await handle_incoming_message(
								buffer, Config.MSG_SRC_UART
							)
							buffer = ''
					# Handle backspace key code (ASCII 127)
					elif ord(char) == 127:
						if len(buffer) > 0:
							buffer = buffer[:-1]
					else:
						buffer += char

		# Yield execution back to the uasyncio event loop for 20ms
		await asyncio.sleep_ms(20)


# ==============================================================================
# MAIN ENTRY POINT & EVENT LOOP INITIALIZATION
# ==============================================================================
async def main() -> None:
	"""
	Initializes hardware peripherals and schedules background tasks concurrently
	inside the primary uasyncio event loop.
	"""
	print('\n--- Pico Motor Controller ---')

	MOTORCTRL.max_speed_val = 200  # work out best value from experimentation
	MOTORCTRL.stop()

	sensors.set_analogue_trigger(0, 9000)  # just an example

	# Assign message callback
	ws_svr.on_message = handle_incoming_message

	# Run WebSocket server and wifi manager concurrently with the CLI task
	asyncio.create_task(ws_svr.start())
	asyncio.create_task(cli_task())
	asyncio.create_task(uart_cli_task())
	asyncio.create_task(sensor_supervisor_task())

	display.println(1, 'Alive!')  # If OLED display fitted

	while True:
		await asyncio.sleep(1)


try:
	asyncio.run(main())
except KeyboardInterrupt:
	print('\nExecution interrupted. Shutting down...')
