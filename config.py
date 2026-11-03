from machine import Pin


class Config:
	WIFI_SSID = 'Minerva'
	WIFI_PASS = 'CezanneZola'

	# Pin Assignments
	MOTOR_L_PWM: Pin = Pin(2)
	MOTOR_L_IN1: Pin = Pin(4)
	MOTOR_L_IN2: Pin = Pin(5)

	MOTOR_R_PWM: Pin = Pin(3)
	MOTOR_R_IN3: Pin = Pin(6)
	MOTOR_R_IN4: Pin = Pin(7)

	# Following are needed only when using analogue sensors
	ADC0: Pin = Pin(26)
	ADC1: Pin = Pin(27)
	ADC2: Pin = Pin(28)

	# Following are for digital sensors - eg, IR proximity sensors
	PROX_SENSOR_L: Pin = Pin(22, Pin.IN, Pin.PULL_UP)
	PROX_SENSOR_R: Pin = Pin(21, Pin.IN, Pin.PULL_UP)
