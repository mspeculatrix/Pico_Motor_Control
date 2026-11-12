"""
Pico 2W Asynchronous Robot Motor Control Hub for the Raspberry Pi Pico 2W.

For a 2-motor robot using an L298-based motor controller board.

Runs a WebSocket server for remote communication.
"""

import json
import random
import sys

import network
import uasyncio as asyncio
import uselect

# ADC needed only if using analogue sensors.
# I2C needed only if using OLED panel or other I2C device.
from machine import I2C, UART, Pin
from micropython import const

from config import Config
from L298_motor_controller import Direction, L298MotorController, Side
from sensors import Sensors  # Needed only if using sensors
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
LEFT: int = const(0)
RIGHT: int = const(1)

MOTORCTRL = L298MotorController(
	Config.MOTOR_L_PWM,
	Config.MOTOR_L_IN1,
	Config.MOTOR_L_IN2,
	Config.MOTOR_R_PWM,
	Config.MOTOR_R_IN3,
	Config.MOTOR_R_IN4,
	Config.MOTOR_BASE_SPEED,
)

# Initialize WebSocket server with credentials and port.
# We'll assign callback functions later.
ws_svr = WebSocketServer(
	port=8080,
	ssid=Config.WIFI_SSID,
	password=Config.WIFI_PASS,
)

# Initialize messaging UART, which will be the main communication channel with
# a controller SBC/MCU on the robot.
comm_port: UART = UART(
	Config.UART_PORT,
	baudrate=Config.UART_BAUD,
	tx=Config.UART_TX,
	rx=Config.UART_RX,
)


# ==============================================================================
# SENSORS - if required
# ==============================================================================
def sensor_isr(pin: Pin) -> None:
	"""
	ISR for when a digital proximity sensor triggers an interrupt by going low.
	This function is needed only if using digital sensors with interrupts.
	This function must be kept extremely lightweight. We're just setting flags
	that will get picked up by sensor_supervisor().
	"""
	global sensors
	if pin == sensors.ds0:
		sensors.add_trigger_flag(sensors.LEFT_TRIGGERED)
	elif pin == sensors.ds1:
		sensors.add_trigger_flag(sensors.RIGHT_TRIGGERED)


# Sensor registers & state
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
update_display: bool = False

# ----- end of OLED block ------------------------------------------------------


# ==============================================================================
# ACTIONS IN RESPONSE TO SENSOR INPUTS - ASYNC TASK
# ==============================================================================
async def execute_action(
	left: bool = False, right: bool = False, analogue: bool = False
) -> None:
	"""
	Repertoire of asynchronous actions using non-blocking sleeps. These provide
	basic obstacle avoidance.

	This is primarily for use with sensors, so if you're not using sensors you
	can probably ditch this (and any line that calls it).

	These are just sample actions. Change them to suit how you want your robot
	to behave. This is where you'll have the most fun coming up with suitable
	manoeuvre algorithms.
	"""

	prev_direction: int = MOTORCTRL._direction_state
	prev_speed: int = MOTORCTRL._speed_state

	# Example decision tree
	if left and right:
		# Both triggered: Head-on collision risk
		await avoidance_manoeuvre('random')

	elif left:
		# Only left triggered -> Obstacle on left, veer/turn right
		await avoidance_manoeuvre('left')

	elif right:
		# Only right triggered -> Obstacle on right, veer/turn left
		await avoidance_manoeuvre('right')

	elif analogue:
		await avoidance_manoeuvre('random')

	# Resume previous motion after manoeuvre
	MOTORCTRL.set_direction(prev_direction)
	MOTORCTRL.set_speed(prev_speed)

	# We'll probably want a more informative message so that, for example,
	# a controller SBC/MCU knows what's happening. But, for now...
	msg: str = f'ACT:L:{left}:R:{right}:A:{analogue}'
	await ws_svr.broadcast(msg)
	await send_cli_msg(msg)


async def avoidance_manoeuvre(dir: str) -> None:
	MOTORCTRL.set_direction(Direction.REV_STR)
	MOTORCTRL.set_speed(MOTORCTRL.speed['SP_SLOW'])
	await asyncio.sleep_ms(Config.AVOID_REV_TIME)
	if dir == 'left':
		MOTORCTRL.set_direction(Direction.ROTATE_L)
	elif dir == 'right':
		MOTORCTRL.set_direction(Direction.ROTATE_R)
	elif dir == 'random':
		if left_or_right() == LEFT:
			MOTORCTRL.set_direction(Direction.ROTATE_L)
		else:
			MOTORCTRL.set_direction(Direction.ROTATE_R)
	else:
		MOTORCTRL.stop()
	await asyncio.sleep_ms(Config.AVOID_TURN_TIME)


# ==============================================================================
# MESSAGING
# ==============================================================================
def ws_msg_print(msg: str) -> None:
	"""
	Function passed to WebSocketServer so that it can pass messages to this
	main program to be forward via the serial connections.

	We could just pass send_cli_msg but I've created this wrapper in case we
	want to get clever about this.
	"""
	# Schedule the async send_cli_msg coroutine into the running event loop
	asyncio.create_task(send_cli_msg(msg))


async def send_cli_msg(msg: str) -> None:
	"""
	Convenience wrapper to send a string to both the UART and CLI interfaces.
	"""
	send_uart_msg(msg)
	print(f'{msg}')


def send_uart_msg(msg: str) -> None:
	"""
	Send a plain text message or telemetry data specifically to the UART port.
	"""
	comm_port.write((f'{msg}\n').encode('utf-8'))


# ==============================================================================
# SENSOR MONITORING - ASYNC TASK
# ==============================================================================
async def sensor_supervisor() -> None:
	"""
	Runs concurrently in the event loop. Monitors digital sensor flags (as set
	by the ISR) and analogue sensors, triggering non-blocking actions.

	The digital flags are set by the sensor_isr interrupt service routine. The
	analogue sensor state is determined by calling is_analogue_triggered(n)
	which in turn calls the analogue instance's is_triggered() method which
	performs a read, compares it against the trigger level and returns a
	boolean.
	"""
	global sensors

	while True:
		await sensors.action_done.wait()  # instant response if action_done set
		# Check digital sensors via the flag register
		triggered: int = sensors.read_and_clear_flag_register()
		if triggered:  # has a non-zero value
			sensors.action_done.clear()
			try:
				# Analyse which sensor(s) fired
				left = bool(triggered & sensors.LEFT_TRIGGERED)
				right = bool(triggered & sensors.RIGHT_TRIGGERED)
				await execute_action(left=left, right=right)
			finally:
				# Reset 'idle' state even if an exception occurs
				sensors.action_done.set()

		# Poll analogue sensors
		# Just checking one here, as an example.
		# Example threshold logic: ADC value below safe limit.
		if sensors.is_analogue_triggered(0):
			sensors.action_done.clear()
			try:
				await execute_action(analogue=True)
			finally:
				sensors.action_done.set()

		await asyncio.sleep_ms(50)  # Check 20 times per second


# ==============================================================================
# WEBSOCKET SERVER MESSAGING CALLBACK
# ==============================================================================
async def handle_incoming_message(
	cmd_str: str, source: int = 0, writer: Optional[asyncio.StreamWriter] = None
) -> None:
	"""
	Callback passed into WebSocketServer to process incoming messages. Also
	used by the two CLI (USB & UART) interfaces. Basically, all incoming
	messages are interpreted here.

	The source parameter indicates where the message came from and have values
	defined in the Config class:

	- Config.MSG_SRC_CLI     USB serial
	- Config.MSG_SRC_UART    UART serial
	- Config.MSG_SRC_WS      WebSocket server

	For each command, the response will be a dict with mandatory key of
	'type', 'cmd' (which just echoes back the command received) and 'result'.
	There may be other keys depending on the command.
	"""
	global MOTORCTRL
	response: dict[str, str | int | float] = {
		'cmd': cmd_str,  # repeat back to sender
		'msg': '',
		'result': 'ERR',  # should be 'OK' or 'ERR'
	}
	cmd_str = cmd_str.strip()

	# Movement commands
	if cmd_str == 'STOP':
		await sensors.action_done.wait()
		MOTORCTRL.stop()
		response['result'] = 'OK'
	elif cmd_str == 'PARK':
		await sensors.action_done.wait()
		MOTORCTRL.park()
		response['result'] = 'OK'
	elif hasattr(Direction, cmd_str):
		await sensors.action_done.wait()
		MOTORCTRL.set_direction(getattr(Direction, cmd_str))
		response['result'] = 'OK'
	elif cmd_str in MOTORCTRL.speed:
		await sensors.action_done.wait()
		MOTORCTRL.set_speed(MOTORCTRL.speed[cmd_str])
		response['result'] = 'OK'

	# Configuration for use with configuration commands in the format:
	# CFG:<CFG_NAME>:<NUMBER>
	elif cmd_str.startswith('CFG:'):
		cfg: list[str] = cmd_str.split(':')
		if len(cfg) == 3:
			if cfg[1] == 'SP_CAL_L':
				MOTORCTRL.set_speed_cal_factor(Side.LEFT, float(cfg[2]))
				response['result'] = 'OK'
			elif cfg[1] == 'SP_CAL_R':
				MOTORCTRL.set_speed_cal_factor(Side.RIGHT, float(cfg[2]))
				response['result'] = 'OK'
			elif cfg[1] == 'BASE_SPEED':
				MOTORCTRL.base_speed = int(cfg[2])
				response['result'] = 'OK'
			elif cfg[1] == 'ADC0_TRIG':
				sensors.set_analogue_trigger(0, int(cfg[2]))
				response['result'] = 'OK'
			else:
				response['result'] = 'ERR'
				response['msg'] = 'UNKNOWN_CONFIG'
		else:
			response['result'] = 'ERR'
			response['msg'] = 'BAD_CMD_FMT'

	# Other commands
	elif cmd_str == 'CONFIG':
		response['type'] = 'CFG'
		response['speed'] = MOTORCTRL.speed_state
		response['base_speed'] = MOTORCTRL.base_speed
		response['direction'] = Direction.get_dir_name(
			MOTORCTRL.direction_state
		)
		response['sp_cal_r'] = MOTORCTRL.speed_cal_factor(Side.RIGHT)
		response['sp_cal_l'] = MOTORCTRL.speed_cal_factor(Side.LEFT)
		response['adc0_trigger'] = sensors.analogue_trigger(0)
		response['result'] = 'OK'

	elif cmd_str == 'STATUS':
		response['clients'] = len(ws_svr.clients)

	elif cmd_str == 'IP':
		response['msg'] = f'{ws_svr.ip}'
		response['result'] = 'OK'

	else:
		response['msg'] = 'UNKNOWN_CMD'
		response['result'] = 'ERR'

	# Decide where to send the response
	if source in (Config.MSG_SRC_CLI, Config.MSG_SRC_UART):
		for key in response:
			msg: str = f'{key}:{response[key]}'
			await send_cli_msg(msg)
	elif source == Config.MSG_SRC_WS:
		if writer is not None:  # respond to specific WS client
			await ws_svr.send(writer, json.dumps(response))
		else:
			await ws_svr.broadcast(response)


# ==============================================================================
# USB-SERIAL & UART CLI - ASYNC TASKS
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
	await send_cli_msg('COM:USB_RDY')

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
	await send_cli_msg('COM:UART_RDY')

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


def left_or_right() -> int:
	return random.getrandbits(1)


# ==============================================================================
# MAIN ENTRY POINT & EVENT LOOP INITIALIZATION
# ==============================================================================
async def main() -> None:
	"""
	Initialises hardware peripherals and schedules background tasks concurrently
	inside the primary uasyncio event loop.
	"""
	global update_display

	# Assign message callbacks
	ws_svr.on_message = handle_incoming_message
	ws_svr.prt_msg = ws_msg_print

	await send_cli_msg('SYS:RUNNING')

	display.clear()  # If OLED display fitted
	display.show()

	MOTORCTRL.stop()
	# Set default calibration
	MOTORCTRL.set_speed_cal_factor(Side.LEFT, Config.MOTOR_L_DEF_CAL)
	MOTORCTRL.set_speed_cal_factor(Side.RIGHT, Config.MOTOR_R_DEF_CAL)

	sensors.set_analogue_trigger(0, 10)  # just an example

	# Run WebSocket server and wifi manager concurrently with the CLI task
	asyncio.create_task(ws_svr.start())
	asyncio.create_task(cli_task())
	asyncio.create_task(uart_cli_task())
	asyncio.create_task(sensor_supervisor())

	display.printstr_double(0, 0, 'Alive!')  # If OLED display fitted
	display.show()

	ip: str = ''

	while True:
		if ip != ws_svr.ip:
			update_display = True
		if update_display:
			ip = ws_svr.ip
			display.println(7, ip)
			display.show()
			update_display = False
		await asyncio.sleep(1)


try:
	asyncio.run(main())
except KeyboardInterrupt:
	# Clean up network and stop motors
	try:
		MOTORCTRL.stop()
		network.WLAN(network.STA_IF).active(False)
	except Exception:
		pass
	send_uart_msg('SYS:SHUTDOWN')
	print('SYS:SHUTDOWN')
