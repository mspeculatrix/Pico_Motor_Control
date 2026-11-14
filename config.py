from machine import Pin
from micropython import const


class Config:
	"""
	Basic configuration constants and default values.
	"""

	WIFI_SSID = 'mySSID'  # Your wifi SSID goes here
	WIFI_PASS = 'myPassword'  # Your super-secret wifi password goes here

	# Pin Assignments
	MOTOR_L_PWM: Pin = Pin(2)
	MOTOR_L_IN1: Pin = Pin(4)
	MOTOR_L_IN2: Pin = Pin(6)
	MOTOR_L_DEF_CAL: float = 1.0

	MOTOR_R_PWM: Pin = Pin(3)
	MOTOR_R_IN3: Pin = Pin(5)
	MOTOR_R_IN4: Pin = Pin(7)
	MOTOR_R_DEF_CAL: float = 0.6  # Right motor is much faster on my machine

	# The value (0-255) that will be given to the L298MotorController instance
	# as the value for the lowest moving speed (CRAWL), also known as the
	# 'breakout' speed. Anything less will leave the motor stalled.
	MOTOR_BASE_SPEED: int = const(100)

	# Periods (in ms) to perform reversing and turning when carrying out
	# obstacle avoidance manoeuvres.
	AVOID_REV_TIME: int = 1500
	AVOID_TURN_TIME: int = 800

	# Flags used to indicate the source of an incoming message - WebSocket
	# server, UART or USB-serial CLI.
	MSG_SRC_WS: int = const(0)
	MSG_SRC_UART: int = const(1)
	MSG_SRC_CLI: int = const(2)

	# Configuration for UART interface.
	UART_PORT: int = const(0)
	UART_TX: Pin = Pin(0)
	UART_RX: Pin = Pin(1)
	UART_BAUD: int = const(115200)

	# Following are needed only when using analogue sensors
	ADC0: Pin = Pin(26)
	ADC1: Pin = Pin(27)
	ADC2: Pin = Pin(28)

	# Following are for digital sensors - eg, IR proximity sensors - if desired
	PROX_SENSOR_L: Pin = Pin(22, Pin.IN, Pin.PULL_UP)
	PROX_SENSOR_R: Pin = Pin(21, Pin.IN, Pin.PULL_UP)

	# For OLED panel, if used
	SSD1306_I2C_ADDR: int = const(0x3C)
	OLED_I2C_PORT: int = const(0)
	OLED_I2C_SDA: Pin = Pin(20)
	OLED_I2C_SCL: Pin = Pin(21)
	OLED_I2C_FREQ: int = const(400000)
