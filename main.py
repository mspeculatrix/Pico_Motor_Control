"""
Pico 2W Asynchronous Control Hub using the refactored WebSocketServer module
"""

import json
import sys

import uasyncio as asyncio
import uselect

# ADC needed only if using analogue sensors.
# I2C needed only if using OLED panel or other I2C device.
from machine import ADC, I2C, Pin

from config import Config
from L298_1207_motor_controller import (
	Direction,
	L298_1207_MotorController,
	Speed,
)
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

MOTORCTRL = L298_1207_MotorController(
	Config.MOTOR_L_PWM,
	Config.MOTOR_L_IN1,
	Config.MOTOR_L_IN2,
	Config.MOTOR_R_PWM,
	Config.MOTOR_R_IN3,
	Config.MOTOR_R_IN4,
)
# ----- This block needed only if using sensors --------------------------------

# Analogue sensors
analogue_sensor_0: ADC = ADC(Config.ADC0)
analogue_sensor_1: ADC = ADC(Config.ADC1)
analogue_sensor_2: ADC = ADC(Config.ADC2)

# Digital sensors
prox_sensor_L: Pin = Config.PROX_SENSOR_L
prox_sensor_R: Pin = Config.PROX_SENSOR_R

# Sensor registers & state
sensor_register: int = 0
is_avoiding: bool = False


class SensorFlags:
	LEFT_TRIGGERED = 0x01
	RIGHT_TRIGGERED = 0x02


# ------------------------------------------------------------------------------

# If using an OLED display on I2C0
i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
# Create display instance
display: SSD1306 = SSD1306(i2c)

# Initialize WebSocket server with credentials, callback, and port
ws_svr = WebSocketServer(
	port=8080, ssid=Config.WIFI_SSID, password=Config.WIFI_PASS
)


async def execute_action(
	left: bool = False, right: bool = False, analogue_trigger: bool = False
) -> None:
	"""
	Repertoire of asynchronous actions using non-blocking sleeps. This is
	primarily for use with sensors.

	These are just sample actions. Change them to suit how you want your robot
	to respond.
	"""
	print(f'[AVOIDANCE] Triggered! L={left}, R={right}, ADC={analogue_trigger}')

	# Example decision tree
	if left and right:
		# Both triggered: Head-on collision risk -> Backup straight, turn hard right
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.SLOW)
		await asyncio.sleep_ms(2000)  # Reverse for 2 seconds

		MOTORCTRL.set_direction(Direction.ROTATE_R)
		MOTORCTRL.set_speed(Speed.NORMAL)
		await asyncio.sleep_ms(1000)  # Turn right for 1 second

	elif left:
		# Only left triggered -> Obstacle on left, veer/turn right
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.CRAWL)
		await asyncio.sleep_ms(1000)

		MOTORCTRL.set_direction(Direction.ROTATE_R)
		MOTORCTRL.set_speed(Speed.SLOW)
		await asyncio.sleep_ms(800)

	elif right:
		# Only right triggered -> Obstacle on right, veer/turn left
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.CRAWL)
		await asyncio.sleep_ms(1000)

		MOTORCTRL.set_direction(Direction.ROTATE_L)
		MOTORCTRL.set_speed(Speed.SLOW)
		await asyncio.sleep_ms(800)

	elif analogue_trigger:
		# Analogue sensor close proximity warning
		MOTORCTRL.set_direction(Direction.REV_STR)
		MOTORCTRL.set_speed(Speed.SLOW)
		await asyncio.sleep_ms(1500)

	# Bring motors to a controlled stop after manoeuvre
	MOTORCTRL.stop()
	print('[AVOIDANCE] Manoeuvre complete. Resuming normal operations.')


async def sensor_supervisor_task() -> None:
	"""
	Runs concurrently in the event loop. Monitors digital sensor flags
	and analogue rangefinders, triggering non-blocking avoidance maneuvers.
	"""
	global sensor_register, is_avoiding

	print('[SUPERVISOR] Sensor monitoring active.')
	while True:
		if not is_avoiding:
			# Check Digital Sensors via the Flag Register
			triggered: int = sensor_register
			if triggered:
				is_avoiding = True
				sensor_register = 0  # Reset register

				# Analyze which sensor(s) fired
				left = bool(triggered & SensorFlags.LEFT_TRIGGERED)
				right = bool(triggered & SensorFlags.RIGHT_TRIGGERED)

				await execute_action(left=left, right=right)
				is_avoiding = False

			# Poll analogue sensors
			# Example threshold logic: ADC value below safe limit
			dist_val: int = analogue_sensor_0.read_u16()
			if dist_val < 10000:  # Tune threshold based on your hardware
				is_avoiding = True
				await execute_action(analogue_trigger=True)
				is_avoiding = False

		await asyncio.sleep_ms(50)  # Check 20 times per second


def sensor_isr(pin: Pin) -> None:
	"""
	This function is needed only if using digital sensors with interrupts.
	This function must be kept extremely lightweight.
	"""
	global sensor_register
	if pin == prox_sensor_L:
		sensor_register |= SensorFlags.LEFT_TRIGGERED
	elif pin == prox_sensor_R:
		sensor_register |= SensorFlags.RIGHT_TRIGGERED

	# Immediate safety stop at the hardware/interrupt level
	MOTORCTRL.stop()


def setup_hardware() -> None:
	global MOTORCTRL
	MOTORCTRL.max_speed_val = 200  # work out best value from experimentation
	MOTORCTRL.stop()

	# If using digital sensors - set up interrupts
	prox_sensor_L.irq(trigger=Pin.IRQ_FALLING, handler=sensor_isr)
	prox_sensor_R.irq(trigger=Pin.IRQ_FALLING, handler=sensor_isr)

	print('[HARDWARE] Motors and Sensor IRQ initialized.')


# ==============================================================================
# CORE COMMAND ROUTER
# ==============================================================================
async def handle_incoming_message(
	cmd_str: str, writer: Optional[asyncio.StreamWriter] = None
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
		MOTORCTRL.stop()
	elif cmd_str == 'PARK':
		MOTORCTRL.park()
	elif hasattr(Direction, cmd_str):
		MOTORCTRL.set_direction(getattr(Direction, cmd_str))
	elif hasattr(Speed, cmd_str):
		MOTORCTRL.set_speed(getattr(Speed, cmd_str))

	# Other commands
	elif cmd_str == 'STATUS':
		# sensor_val: int = sensor_pin.value() if sensor_pin else 1
		response['type'] = 'STATE'
		# response['sensor'] = sensor_val
		response['clients'] = len(ws_svr.clients)
	elif cmd_str == 'IP':
		response['type'] = 'STATE'
		response['result'] = f'{ws_svr.ip}'
	else:
		response['type'] = 'ERROR'
		response['result'] = 'Unknown command'

	for key in response:
		print(f'[{key}] {response[key]}')
	if writer is not None:  # respond to specific client
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
						await handle_incoming_message(buffer)
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


# ==============================================================================
# MAIN ENTRY POINT & EVENT LOOP INITIALIZATION
# ==============================================================================
async def main() -> None:
	"""
	Initializes hardware peripherals and schedules background tasks concurrently
	inside the primary uasyncio event loop.
	"""
	print('\n--- Pico WebSocket Server ---')
	setup_hardware()

	# Assign message callback
	ws_svr.on_message = handle_incoming_message

	# Run WebSocket server and wifi manager concurrently with the CLI task
	asyncio.create_task(ws_svr.start())
	asyncio.create_task(cli_task())
	asyncio.create_task(sensor_supervisor_task())

	while True:
		await asyncio.sleep(1)


try:
	asyncio.run(main())
except KeyboardInterrupt:
	print('\nExecution interrupted. Shutting down...')
