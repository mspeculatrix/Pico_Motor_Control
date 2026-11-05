# PICO MOTOR CONTROL

This project is built around a commonly available dual-channel motor controller that uses the L298 dual H-bridge chip. For example, you can find it on [AliExpress](https://fr.aliexpress.com/item/32818921042.html).

![L298 Motor Controller](Reference/L298_Motor_Controller.png)

For more information on this, see the [L298_Motor_Controller.md](Documentation/L298_Motor_Controller.md) file.

We're controlling this with a Raspberry Pi Pico 2W running MicroPython.

The project is also oriented somewhat to my Pico Motor Control board, but you don't need to use that. A Pico on a breadboard, stripboard or your own PCB would work just as well. The code does include elements relating to the digital and analogue sensor connections available on this board, but you can always strip out those bits or repurpose them for your own needs.

## INTERFACES

The code provides for no fewer than three interfaces for message passing and command and control.

- **WebSocket server**: on port 8080 over wifi offers a remote connection. You can, for example, control the motors from a web app running on your server or laptop.
- **UART serial connection**: using UART0 on pins GP0 and GP1. The main purpose of this is to allow the Pico to communicate with another microcontroller or computer. You _could_ talk to it using a USB-to-UART cable (bearing in mind that the pins are 3.3V), but there is a better option, which is...
- **Serial-USB**: A serial connection via the Pico's USB port. All you need to plug into this is a normal USB cable. This interface is intended for debugging as it's not so useful when the robot is running around on the floor.

All incoming messages from these interfaces are chanelled through the `handle_incoming_message()` function, which decides what to do with them. If the message came in via _either_ the UART _or_ the CLI, the response is sent to both. If the message came in via the WS server, the response is broadcast to all clients connected to that server (although the WS code does allow for responding to specific clients).

## SENSORS

You don't need to have any sensors attached to use this code. But it does include code for two types of sensor:

- **Digital proximity sensors**: Both the board and the code assume sensors that produce a normally high signal at +5V (the board includes level shifting for compatibility with the Pico) and which switch low when the sensor comes within a predetermined distance from a sensor. This will generate an interrupt. What you do with that interrupt is up to you. As far as the board is concerned, the sensor has a 10k pullup on the digital output. The code & board provide for two of these sensors. I'm using the E18-D80NK.
- **Analogue sensors**: The board and code allow for three such sensors, about which they make certain assumptions: that the sensor requires +5V power and supplies an analogue signal that does not go above +3.3V. If you use a sensor that produces a higher output voltage, you'll need to step it down somehow. I'm using one of these sensors with a Sharp infrared rangefinder (the GP2Y0A21YK0F).

Information about the sensors I'm using is in the `Reference/Sensors/` folder. But, like I said, you don't have to use them. I've tried to indicate within the code which parts you can remove if not using sensors.

## OLED PANEL

This is another optional element. On the board, I've broken out the I2C0 port to run an SSD1306 OLED panel. You could use it for other sensors or devices - or nothing. The code sets up the I2C port and imports my basic SSD1306 library - but again, these are optional.
