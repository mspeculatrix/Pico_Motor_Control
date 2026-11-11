from machine import PWM, Pin
from micropython import const

"""
This code assumes that the left motor is connected to ENA, IN1 & IN2 (Motor A)
and the right motor to ENB, IN3 & IN4 (Motor B).
"""


class Side:
	"""
	These values can be used as masks, but also as general-purpose constants.
	"""

	LEFT: int = const(0b1100)
	RIGHT: int = const(0b0011)


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

	The VEER directions have the same values as STR (straight). But the code
	applies half-speed to the in-turn motor.

	The TURN directions stop the in-turn motor.

	We only need 4-bit values - the lowest four bits are the ones that do the
	work by determining the signal values for IN1, IN2, IN3 & IN4.

	I've added bits 5 & 6 simply so that each property has a unique value.
	For example, without these higher bits, the values for FWD_STR, FWD_VEER_L
	and FWD_VEER_R would all be 0b1010.
	This could be useful in lots of situations but is actually required by
	the reverse lookup class method. The actual values of bits 5 & 6 are
	arbitrary.
	"""

	DIR_STOP: int = const(0b000000)
	FWD_STR: int = const(0b001010)
	FWD_VEER_L: int = const(0b011010)
	FWD_VEER_R: int = const(0b101010)
	FWD_TURN_L: int = const(0b000010)
	FWD_TURN_R: int = const(0b001000)
	REV_STR: int = const(0b000101)
	REV_TURN_L: int = const(0b000001)
	REV_TURN_R: int = const(0b000100)
	REV_VEER_L: int = const(0b010101)
	REV_VEER_R: int = const(0b100101)
	ROTATE_L: int = const(0b000110)
	ROTATE_R: int = const(0b001001)

	@classmethod
	def get_dir_name(cls, value: int) -> str:
		"""
		Reverse lookup: returns the string name of the direction constant
		for a given integer value. This is for use with the web client.
		"""
		for name, val in cls.__dict__.items():
			# Skip private/built-in attributes and methods
			if not name.startswith('_') and val == value:
				return name
		return 'UNKNOWN'


class Speed:
	"""
	These are in the range 0 - 255. The actual values will be mapped
	appropriately in set_speed() using the _max_speed_val. But here,
	STOP should always be 0 and MAX should be 255 with the other values
	distributed between them.
	"""

	SP_STOP: int = const(0)
	SP_CRAWL: int = const(70)
	SP_SLOW: int = const(95)
	SP_NORMAL: int = const(127)
	SP_FAST: int = const(190)
	SP_MAX: int = const(255)

	@classmethod
	def get_speed_name(cls, value: int) -> str:
		"""
		Reverse lookup: returns the string name of the speed constant
		for a given integer value. This is for use with the web client.
		"""
		for name, val in cls.__dict__.items():
			# Skip private/built-in attributes
			if not name.startswith('_') and val == value:
				return name
		return 'UNKNOWN'


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
		self._ena_ctrl.freq(1000)  # See dev notes
		self._ena_ctrl.duty_u16(0)
		self._enb_ctrl = PWM(enb_pin)
		self._enb_ctrl.freq(1000)
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

		# These are calibration factors to apply to speed values to compensate
		# for any speed discrepancies between the left and right motors.
		# The numbers must be a maximum of 1.
		self._speed_cal_factor_l: float = 1
		self._speed_cal_factor_r: float = 1

		# The following state variables are used to store the last given
		# speed and direction settings. They are not zeroed out when a STOP
		# value is given. That way, when start() is used, the motor resumes
		# its previous values.
		self._direction_state: int = Direction.DIR_STOP
		self._speed_state: int = Speed.SP_STOP

	@property
	def direction_state(self) -> int:
		return self._direction_state

	@property
	def max_speed_val(self) -> int:
		return self._max_speed_val

	@max_speed_val.setter
	def max_speed_val(self, value: int) -> None:
		# Constrain to range 0-255
		value = max(0, min(255, value))
		self._max_speed_val = value

	def park(self) -> None:
		self.set_direction(Direction.DIR_STOP)
		self.set_speed(Speed.SP_STOP)

	def speed_cal_factor(self, side: int) -> float:
		"""
		Get the speed_cal_factor for the left or right motor. If an incorrect
		value is passed for side, return 1 as a safe default
		"""
		if side == Side.LEFT:
			return self._speed_cal_factor_l
		elif side == Side.RIGHT:
			return self._speed_cal_factor_r
		else:
			return 1.0

	def set_speed_cal_factor(self, side: int, val: float) -> None:
		"""
		Set the speed_cal_factor for the left or right motor.
		"""
		if val > 1.0 or val < 0.0:
			val = 1.0
		if side == Side.LEFT:
			self._speed_cal_factor_l = val
		else:
			self._speed_cal_factor_r = val

	def set_speed(self, speed: int) -> None:
		"""
		Value should be in range 0-255.
		"""
		self._speed_state = speed  # keep internally for later use
		# Ensure input value is in valid range
		speed = max(0, min(255, speed))
		# Now map this to our _max_speed_val limit
		speed = self._map_int_val(speed, 0, 255, 0, self._max_speed_val)
		# Map this value to PWM 16-bit value range

		duty_l: int = int((speed / 255.0) * 65535 * self._speed_cal_factor_l)
		duty_r: int = int((speed / 255.0) * 65535 * self._speed_cal_factor_r)

		if (
			self._direction_state == Direction.FWD_VEER_L
			or Direction.REV_VEER_L
		):
			# Left motor needs to be half speed
			self._ena_ctrl.duty_u16(int(duty_l / 2))
			self._enb_ctrl.duty_u16(duty_r)
		elif (
			self._direction_state == Direction.FWD_VEER_R
			or Direction.REV_VEER_R
		):
			# Right motor needs to be half speed
			self._ena_ctrl.duty_u16(duty_l)
			self._enb_ctrl.duty_u16(int(duty_r / 2))
		else:  # Apply same speed to both sides
			self._ena_ctrl.duty_u16(duty_l)
			self._enb_ctrl.duty_u16(duty_r)

	@property
	def speed_state(self) -> int:
		return self._speed_state

	def set_direction(self, dir: int) -> None:
		"""
		The dir param contains a 4-bit value, as defined in the Direction class.
		"""
		if dir != Direction.DIR_STOP:
			self._direction_state = dir  # keep internally for later use

		left_val: int = (dir & Side.LEFT) >> 2
		right_val: int = dir & Side.RIGHT

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
		self.set_direction(Direction.DIR_STOP)
		self.set_speed(Speed.SP_STOP)

	def _map_int_val(
		self, value: int, fromMin: int, fromMax: int, toMin: int, toMax: int
	) -> int:
		"""
		Map integer value from one range to another range.
		"""
		return (value - fromMin) * (toMax - toMin) // (
			fromMax - fromMin
		) + toMin
