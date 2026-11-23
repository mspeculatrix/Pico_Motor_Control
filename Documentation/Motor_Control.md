# MOTOR CONTROL

In either direction (forward or backwards) there are the following modes of movement:

| MODE     | MOVEMENT                                        |
|----------|-------------------------------------------------|
| STRAIGHT | Both motors same speed                          |
| VEER     | One motor at set speed, the other at half speed |
| TURN     | One motor at set speed, the other stopped       |
| ROTATE   | Both motors set speed, one forward, one reverse |

Assignments:

- Left (A) Motor: IN1, IN2, ENA, OUT1
- Right (B) Motor: IN3, IN4, ENB, OUT2

| DIRECTION | MODE     | TURN   | IN1 | IN2 | IN3 | IN4 | VAL  |
|-----------|----------|:------:|:---:|:---:|:---:|:---:|:----:|
| STOP      |    --    |  --    |  0  |  0  |  0  |  0  | 0000 |
| FORWORD   | STRAIGHT |  --    |  1  |  0  |  1  |  0  | 1010 |
| FORWORD   | VEER     |  L     |  1  |  0  |  1  |  0  | 1010 |
| FORWORD   | VEER     |  R     |  1  |  0  |  1  |  0  | 1010 |
| FORWORD   | TURN     |  L     |  0  |  0  |  1  |  0  | 0010 |
| FORWORD   | TURN     |  R     |  1  |  0  |  0  |  0  | 1000 |
| REVERSE   | STRAIGHT |  --    |  0  |  1  |  0  |  1  | 0101 |
| REVERSE   | VEER     |  L     |  0  |  1  |  0  |  1  | 0101 |
| REVERSE   | VEER     |  R     |  0  |  1  |  0  |  1  | 0101 |
| REVERSE   | TURN     |  L     |  0  |  0  |  0  |  1  | 0001 |
| REVERSE   | TURN     |  R     |  0  |  1  |  0  |  0  | 0100 |
| --        | ROTATE   |  L     |  0  |  1  |  1  |  0  | 0110 |
| --        | ROTATE   |  R     |  1  |  0  |  0  |  1  | 1001 |

VEER is the same as STRAIGHT but the turning motion is achieved via motor speeds.

So we can define some constants.

I've added bits 5 & 6 simply so that each property has a unique value. For example, without these higher bits, the values for FWD_STR, FWD_VEER_L and FWD_VEER_R would all be 1010. These extra bits could be useful in lots of situations but are actually required by at least one function.

The values for bits 5 & 6 are:

- **00** for straight
- **01** for left turns
- **10** for right turns

- DIR_STOP:    00 00 00
- FWD_STR:     00 10 10
- FWD_VEER_L:  01 10 10
- FWD_VEER_R:  10 10 10
- FWD_TURN_L:  01 00 10
- FWD_TURN_R:  10 10 00
- REV_STR:     00 01 01
- REV_TURN_L:  01 00 01
- REV_TURN_R:  10 01 00
- REV_VEER_L:  01 01 01
- REV_VEER_R:  10 01 01
- ROTATE_L:    01 01 10
- ROTATE_R:    10 10 01
