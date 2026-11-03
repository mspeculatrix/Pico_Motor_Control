from machine import Pin
from micropython import const


class Config:
	WIFI_SSID = 'MySSID'  # Your wifi SSID goes here
	WIFI_PASS = 'MyPassword'  # Your super-secret wifi password goes here

	# Pin Assignments
	MOTOR_L_PWM: Pin = Pin(2)
	MOTOR_L_IN1: Pin = Pin(4)
	MOTOR_L_IN2: Pin = Pin(5)

	MOTOR_R_PWM: Pin = Pin(3)
	MOTOR_R_IN3: Pin = Pin(6)
	MOTOR_R_IN4: Pin = Pin(7)

	MSG_SRC_WS: int = const(0)
	MSG_SRC_UART: int = const(1)
	MSG_SRC_CLI: int = const(2)

	# Following are needed only when using analogue sensors
	ADC0: Pin = Pin(26)
	ASENS0_THRESHOLD: int = 10000
	ADC1: Pin = Pin(27)
	ADC2: Pin = Pin(28)

	# Following are for digital sensors - eg, IR proximity sensors
	PROX_SENSOR_L: Pin = Pin(22, Pin.IN, Pin.PULL_UP)
	PROX_SENSOR_R: Pin = Pin(21, Pin.IN, Pin.PULL_UP)

	# For OLED panel, if used
	SSD1306_I2C_ADDR: int = const(0x3C)
