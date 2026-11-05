import uasyncio as asyncio
from machine import ADC, Pin
from micropython import const

try:
	from typing import TYPE_CHECKING
except ImportError:
	TYPE_CHECKING = False

if TYPE_CHECKING:
	from typing import Callable


class ADCchannel:
	def __init__(self, pin: Pin) -> None:
		self._pin: Pin = pin
		self._trigger: int = 10000
		self._adc: ADC = ADC(pin)

	def read(self) -> int:
		return self._adc.read_u16()

	def set_trigger(self, value: int) -> None:
		self._trigger = value

	@property
	def is_triggered(self) -> bool:
		return self.read() < self._trigger  # True if below threshold distance


class Sensors:
	# Flags
	LEFT_TRIGGERED: int = const(0x01)
	RIGHT_TRIGGERED: int = const(0x02)

	def __init__(
		self, ds0: Pin, ds1: Pin, as0: Pin, as1: Pin, as2: Pin, isr
	) -> None:
		self.ds0: Pin = ds0
		self.ds1: Pin = ds1
		self._as0: ADCchannel = ADCchannel(as0)
		self._as1: ADCchannel = ADCchannel(as1)
		self._as2: ADCchannel = ADCchannel(as2)
		self._adcs: list[ADCchannel] = [self._as0, self._as1, self._as2]
		self._register: int = 0
		self._isr: Callable = isr
		self.ds0.irq(trigger=Pin.IRQ_FALLING, handler=self._isr)
		self.ds1.irq(trigger=Pin.IRQ_FALLING, handler=self._isr)
		self.action_done = asyncio.Event()
		self.action_done.set()  # idle at startup

	def add_trigger_flag(self, flag: int) -> None:
		"""Atomic-safe trigger flag setter for use inside ISRs."""
		self._register |= flag

	def read_and_clear_flag_register(self) -> int:
		"""Atomically clear and return the current register flags."""
		val: int = self._register
		self._register = 0
		return val

	def is_analogue_triggered(self, channel: int) -> bool:
		return self._adcs[channel].is_triggered

	def read_analogue(self, channel: int) -> int:
		return self._adcs[channel].read()

	def set_analogue_trigger(self, channel: int, value: int) -> None:
		self._adcs[channel].set_trigger(value)
