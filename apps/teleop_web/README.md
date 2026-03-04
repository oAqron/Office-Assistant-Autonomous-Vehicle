# vehicle_web_teleop

Jetson-hosted WebSocket teleop server that bridges a browser joystick UI to
Dynamixel AX/RX/MX motors over RS485 (Protocol 1.0).

## Architecture

```
Browser ──WS──► ws_server.py ──► session.py (lock + heartbeat)
                                     │
                                     ▼
                              safety_core.py (deadman 500 ms, clamp ±1)
                                     │
                                     ▼
                            twist_mapper.py (optional speed-scale hook)
                                     │
                                     ▼
                              bridge.py (float → 9-byte custom packet)
                                     │
                                     ▼
                            rs485_port.py (pyserial, async executor)
                                     │
                             /dev/ttyTHS1 (Jetson UART @ 115200)
                                     │
                             robot motor controller MCU
```

### Safety guarantees
| Guarantee | Mechanism |
|---|---|
| Deadman timeout | `safety_core` stops motors if no `cmd_vel` in 500 ms |
| Stop on drop | WS disconnect triggers immediate `send_stop()` |
| Single controller | `session.py` issues one exclusive lock; second client is rejected |
| Velocity clamping | Inputs normalised to `[-1.0, 1.0]` before motor write |

## Hardware setup

| Component | Value |
|---|---|
| Serial port | `/dev/ttyTHS1` (Jetson Orin Nano hardware UART) |
| Baudrate | 115 200 bps |
| Robot kinematics | Holonomic / omnidirectional (vx + vy strafe + vz yaw) |

## Quick start

```bash
# 1. Install (Jetson, Python 3.10+)
pip install -e "vehicle_web_teleop[dev]"

# 2. Run dev server (edit serial port first)
bash vehicle_web_teleop/scripts/run_dev.sh

# 3. Open browser
http://<jetson-ip>:8080
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VWT_SERIAL_PORT` | `/dev/ttyTHS1` | UART device path |
| `VWT_BAUD` | `115200` | Serial baudrate |
| `VWT_HOST` | `0.0.0.0` | Server bind address |
| `VWT_PORT` | `8080` | HTTP/WS port |
| `VWT_DEADMAN_MS` | `500` | Deadman timeout in milliseconds |
| `VWT_VX_SCALE` | `100` | Forward/reverse scale (matches `1.0 * g * 100` at g=1) |
| `VWT_VY_SCALE` | `100` | Strafe scale |
| `VWT_VZ_SCALE` | `500` | Yaw scale (matches `5.0 * g * 100` at g=1) |
| `VWT_HB_TIMEOUT_S` | `5.0` | Session heartbeat timeout (seconds) |

## ROS 2 integration (future)

`safety_core.py` and `twist_mapper.py` are intentionally decoupled from the
transport layer.  A ROS 2 node can import `SafetyCore` and call
`await safety_core.submit(TwistCommand(...))` from a `/cmd_vel` subscription
without touching any other file.  The motor bridge stays identical.

## Packet protocol (from existing keyboard teleop script)

`bridge.py` replicates `assemble_packet()` exactly:

```python
# Original keyboard teleop (replicated in bridge.py):
packet = bytearray.fromhex('3E 01 09')
packet.extend(struct.pack('>h', int(linear_x  * vx_scale)))   # forward / reverse
packet.extend(struct.pack('>h', int(linear_y  * vy_scale)))   # strafe
packet.extend(struct.pack('>h', int(angular_z * vz_scale)))   # yaw
# Total: 9 bytes, no checksum
```

Keyboard-to-axis mapping (preserved from original script):

| Key | Axis | Value |
|---|---|---|
| `w` | vx | `+g x 100` |
| `s` | vx | `-g x 100` |
| `a` | vy | `-g x 100` |
| `d` | vy | `+g x 100` |
| `q` | vz | `-5g x 100` |
| `e` | vz | `+5g x 100` |

Web joystick: drag Y-axis = vx (forward/reverse), drag X-axis = vy (strafe).
Q/E buttons and keyboard Q/E keys control vz (yaw).
