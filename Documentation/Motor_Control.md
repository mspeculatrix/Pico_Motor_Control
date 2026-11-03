# MOTOR CONTROL

In either direction (forward or backwards) there are the following modes of movement:

| MODE     | MOVEMENT                                        |
|----------|-------------------------------------------------|
| STRAIGHT | Both motors same speed                          |
| CURVE    | One motor at set speed, the other at half speed |
| VEER     | One motor at set speed, the other stopped       |
| ROTATE   | Both motors set speed, one forward, one reverse |

Assignments:

- Left Motor: IN1, IN2, ENA, OUT1
- Right motor: IN3, IN4, ENB, OUT2

| DIRECTION | MODE     | TURN   | IN1 | IN2 | IN3 | IN4 | VAL  |
|-----------|----------|:------:|:---:|:---:|:---:|:---:|      |
| STOP      |    --    |  --    |  0  |  0  |  0  |  0  | 0000 |
| FORWORD   | STRAIGHT |  --    |  1  |  0  |  1  |  0  | 1010 |
| FORWORD   | VEER     |  L     |  0  |  0  |  1  |  0  | 0010 |
| FORWORD   | VEER     |  R     |  1  |  0  |  0  |  0  | 1000 |
| REVERSE   | STRAIGHT |  --    |  0  |  1  |  0  |  1  | 0101 |
| REVERSE   | VEER     |  L     |  0  |  0  |  0  |  1  | 0001 |
| REVERSE   | VEER     |  R     |  0  |  1  |  0  |  0  | 0100 |
| --        | ROTATE   |  L     |  0  |  1  |  1  |  0  | 0110 |
| --        | ROTATE   |  R     |  1  |  0  |  0  |  1  | 1001 |

CURVE is the same as STRAIGHT but is determined through motor speeds.

So we can define some constants:

STOP        00 00
FWD_STR     10 10
FWD_VEER_L  00 10
FWD_VEER_R  10 00

REV_STR     01 01
REV_VEER_L  00 01
REV_VEER_R  01 00

ROTATE_L    01 10
ROTATE_R    10 01
