from machine import PWM, Pin
from micropython import const

"""
This code assumes that the left motor is connected to ENA, IN1 & IN2 and the
right motor to ENB, IN3 & IN4.
"""


class Direction:
	"""
	These values contain bit values to pass to the INx pins to control the
	forward/reverse direction.
	The upper two bits are for the left motor and the lower two for	the right
	motor.
	Within each pair, the left bit is for ina (IN1/IN3 depending on motor)
	and the right bit for inb (IN2/IN4).
	Because these values contain the settings for both motors, the main
	program can pass the same value to both motor instances.
	"""

	STOP: int = const(0b0000)
	FWD_STR: int = const(0b1010)
	FWD_VEER_L: int = const(0b0010)
	FWD_VEER_R: int = const(0b1000)
	REV_STR: int = const(0b0101)
	REV_VEER_L: int = const(0b0001)
	REV_VEER_R: int = const(0b0100)
	ROTATE_L: int = const(0b0110)
	ROTATE_R: int = const(0b1001)


class Speed:
	"""
	These are in the range 0 - 255. The actual values will be mapped
	appropriately in set_speed() using the _max_speed_val. But here,
	STOP should always be 0 and MAX should be 255 with the other values
	distributed between them.

	PARKED is different to STOP. If the speed is set to STOP, this doesn't
	change the stored speed state, so that issuing a start() resumes at the
	previously set speed. Setting the speed to PARKED does change the stored
	speed state to 0. So subsequently using start() won't result in any
	movement unless set_speed() is also used.

	Also, setting the speed to PARKED also resets the direction value to
	FWD_STR.
	"""

	PARKED: int = const(0)
	STOP: int = const(0)
	CRAWL: int = const(40)
	SLOW: int = const(80)
	NORMAL: int = const(127)
	BRISK: int = const(160)
	FAST: int = const(200)
	MAX: int = const(255)


class L298MotorController:
	def __init__(
		self,
		ena_pin: Pin,
		in1_pin: Pin,
		in2_pin: Pin,
		enb_pin: Pin,
		in3_pin: Pin,
		in4_pin: Pin,
	) -> None:
		self._ena_ctrl = PWM(ena_pin)
		self._ena_ctrl.freq(2500)  # See dev notes
		self._ena_ctrl.duty_u16(0)
		self._enb_ctrl = PWM(enb_pin)
		self._enb_ctrl.freq(2500)
		self._enb_ctrl.duty_u16(0)

		self._in1_pin: Pin = Pin(in1_pin, Pin.OUT)
		self._in2_pin: Pin = Pin(in2_pin, Pin.OUT)
		self._in3_pin: Pin = Pin(in3_pin, Pin.OUT)
		self._in4_pin: Pin = Pin(in4_pin, Pin.OUT)
		self._in1_pin.value(0)
		self._in2_pin.value(0)
		self._in3_pin.value(0)
		self._in4_pin.value(0)

		# _max_speed_val is a value used in set_speed(). It sets the upper limit
		# (in the range 0-255) for values used to actually set the motor speed.
		# The user provides a value in the range of 0-255 and set_speed() maps
		# this to the range 0- _max_speed_val. This is so we can set the maximum
		# value for various motors.
		self._max_speed_val: int = 255

		# The following state variables are used to store the last given
		# speed and direction settings. They are not zeroed out when a STOP
		# value is given. That way, when start() is used, the motor resumes
		# its previous values.
		self._direction_state: int = Direction.STOP
		self._speed_state: int = Speed.STOP

	@property
	def max_speed_val(self) -> int:
		return self._max_speed_val

	@max_speed_val.setter
	def max_speed_val(self, value: int) -> None:
		# Constrain to range 0-255
		value = max(0, min(255, value))
		self._max_speed_val = value

	def park(self) -> None:
		self.set_direction(Direction.STOP)
		self.set_speed(Speed.PARKED)

	def set_speed(self, speed: int) -> None:
		"""value should be in range 0-255"""
		if speed != Speed.STOP:
			self._speed_state = speed  # keep internally for later use
		if speed == Speed.PARKED:
			self._direction_state = Direction.FWD_STR
		# Ensure input value is in valid range
		speed = max(0, min(255, speed))
		# Now map this to our _max_speed_val limit
		speed = self._map_int_val(speed, 0, 255, 0, self._max_speed_val)
		# Map this value to PWM 16-bit value range
		duty: int = int((speed / 255.0) * 65535)
		if (
			self._direction_state == Direction.FWD_VEER_L
			or Direction.REV_VEER_L
		):
			# Left motor needs to be half speed
			self._ena_ctrl.duty_u16(int(duty / 2))
			self._enb_ctrl.duty_u16(duty)
		elif (
			self._direction_state == Direction.FWD_VEER_R
			or Direction.REV_VEER_R
		):
			# Right motor needs to be half speed
			self._ena_ctrl.duty_u16(duty)
			self._enb_ctrl.duty_u16(int(duty / 2))
		else:  # Apply same speed to both sides
			self._ena_ctrl.duty_u16(duty)
			self._enb_ctrl.duty_u16(duty)

	def set_direction(self, dir: int) -> None:
		"""
		The dir param contains a 4-bit value, as defined in the Direction class.
		"""
		if dir != Direction.STOP:
			self._direction_state = dir  # keep internally for later use

		left_val: int = dir >> 2
		right_val: int = dir & 0b0011

		# we now have two 2-bit values
		# The following sets the direction, forward or backward.
		self._in1_pin.value(left_val >> 1)  # MSB
		self._in2_pin.value(left_val & 0b01)  # LSB
		self._in3_pin.value(right_val >> 1)  # MSB
		self._in4_pin.value(right_val & 0b01)  # LSB
		# But we have a special case with 'VEER' in which we need to set the
		# speed of one side to half that of the set speed.
		# So we'll call set_speed() with the internally saved speed state.
		self.set_speed(self._speed_state)

	def start(self) -> None:
		"""
		Start moving with whatever speed and diretion values we last set.
		"""
		self.set_direction(self._direction_state)
		self.set_speed(self._speed_state)

	def stop(self) -> None:
		self.set_direction(Direction.STOP)
		self.set_speed(Speed.STOP)

	def _map_int_val(
		self, value: int, fromMin: int, fromMax: int, toMin: int, toMax: int
	) -> int:
		"""
		Map integer value from one range to another range.
		"""
		return (value - fromMin) * (toMax - toMin) // (
			fromMax - fromMin
		) + toMin
