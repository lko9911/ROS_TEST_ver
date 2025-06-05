import sys
import time
import math
import can
import struct
from enum import IntEnum

CHANNEL = 'COM3'
BITRATE = 250000
TOLERANCE = 1

REDUCTION_RATIOS = {
    0: -46.003,
    1: -46.003,
    2: 28.4998,
    3: 5.5,
    4: -5,
    5: 5
}

JOINT_SEQUENCE = [
    [-3.1412, 0.873, -2.094, -1.222, -1.5708, 0.0],
    [-2.788, -0.5, -1.690, 0.951, 1.935, -3.1412],
    [-3.1412, 0.873, -2.094, -1.222, -1.5708, 0.0],
    [0, 0, 0, 0, 0, 0]
]

NODE_SPEED_PARAMS = {
    0: {'vel': 9.0, 'accel': 8.0, 'decel': 8.0},
    1: {'vel': 9.0, 'accel': 8.0, 'decel': 8.0},
    2: {'vel': 8.5, 'accel': 7.0, 'decel': 7.0},
    3: {'vel': 3.0, 'accel': 2.5, 'decel': 2.5},
    4: {'vel': 6.0, 'accel': 5.5, 'decel': 5.5},
    5: {'vel': 6.0, 'accel': 5.5, 'decel': 5.5},
}

MIN_VEL = 1.0
MIN_ACCEL = 0.8
MIN_DECEL = 0.8

class CommandID(IntEnum):
    Set_Axis_State = 0x07
    Get_Encoder_Estimates = 0x09
    Set_Controller_Mode = 0x0b
    Set_Input_Pos = 0x0c
    Set_Traj_Vel_Limit = 0x11
    Set_Traj_Accel_Limits = 0x12

def generate_can_id(node_id: int, command_id: int) -> int:
    return (node_id << 5) + command_id

def generate_can_message(*values: float) -> bytes:
    float_list = list(values)
    while len(float_list) * 4 < 8:
        float_list.append(0.0)
    return b''.join(struct.pack('<f', v) for v in float_list)[:8]

def clear_can_buffer(bus):
    while True:
        msg = bus.recv(timeout=0.001)
        if msg is None:
            break

def get_pos_estimate(bus: can.Bus, node_id: int) -> float:
    clear_can_buffer(bus)
    can_id = generate_can_id(node_id, CommandID.Get_Encoder_Estimates)
    bus.send(can.Message(arbitration_id=can_id, data=[], is_extended_id=False))
    start_time = time.time()
    while time.time() - start_time < 0.1:
        rx_msg = bus.recv(timeout=0.01)
        if rx_msg and rx_msg.arbitration_id == can_id and len(rx_msg.data) >= 4:
            return struct.unpack('<f', rx_msg.data[0:4])[0]
    raise TimeoutError(f"[에러] Node {node_id} 응답 없음")

def send_input_pos(bus, node_id, input_pos, vel_ff=0.0):
    if abs(input_pos) < 1e-4:
        input_pos = 0.0
        vel_ff = 0.01
    can_id = generate_can_id(node_id, CommandID.Set_Input_Pos)
    payload = generate_can_message(input_pos, vel_ff)
    bus.send(can.Message(arbitration_id=can_id, data=payload, is_extended_id=False))

def send_traj_vel_limit(bus, node_id, vel_limit):
    can_id = generate_can_id(node_id, CommandID.Set_Traj_Vel_Limit)
    payload = generate_can_message(vel_limit)
    bus.send(can.Message(arbitration_id=can_id, data=payload, is_extended_id=False))

def send_traj_accel_limits(bus, node_id, accel, decel):
    can_id = generate_can_id(node_id, CommandID.Set_Traj_Accel_Limits)
    payload = generate_can_message(accel, decel)
    bus.send(can.Message(arbitration_id=can_id, data=payload, is_extended_id=False))

def send_position_control_mode(bus, node_id):
    can_id = generate_can_id(node_id, CommandID.Set_Controller_Mode)
    payload = b'\x03\x00\x00\x00' + b'\x05\x00\x00\x00'
    bus.send(can.Message(arbitration_id=can_id, data=payload, is_extended_id=False))

def send_closed_loop_state(bus, node_id):
    can_id = generate_can_id(node_id, CommandID.Set_Axis_State)
    payload = b'\x08\x00\x00\x00' + b'\x00\x00\x00\x00'
    bus.send(can.Message(arbitration_id=can_id, data=payload, is_extended_id=False))

def wait_until_reached(bus, node_id, target_pos, tolerance=1, max_retry=300):
    retry = 0
    while retry < max_retry:
        try:
            current = get_pos_estimate(bus, node_id)
            error = abs(current - target_pos)
            print(f"[비교] Node {node_id} 현재: {current:.2f}, 목표: {target_pos:.2f}, 오차: {error:.2f}")
            if error <= tolerance:
                return True
        except Exception as e:
            print(f"[에러] 위치 확인 실패: {e}")
        retry += 1
        time.sleep(0.5)
    print(f"[경고] Node {node_id} 목표 도달 실패")
    return False

'''
def initialize_nodes(bus, node_ids):
    for node_id in node_ids:
        send_position_control_mode(bus, node_id)
        time.sleep(0.05)
        send_closed_loop_state(bus, node_id)
        print(f"[초기화] Node {node_id} 완료")
'''

def calculate_normalized_speeds(bus, joint_angles):
    target_positions = {}
    current_positions = {}
    deltas = {}

    for node_id, angle in enumerate(joint_angles):
        reduction = REDUCTION_RATIOS[node_id]
        target_pos = (reduction / 360.0) * math.degrees(angle)
        current_pos = get_pos_estimate(bus, node_id)
        delta = abs(target_pos - current_pos)

        target_positions[node_id] = target_pos
        current_positions[node_id] = current_pos
        deltas[node_id] = delta

    max_delta = max(deltas.values()) if deltas else 1.0

    speeds = {}
    for node_id in target_positions:
        ratio = deltas[node_id] / max_delta if max_delta > 0 else 1.0
        max_params = NODE_SPEED_PARAMS[node_id]
        vel = max(MIN_VEL, max_params['vel'] * ratio)
        accel = max(MIN_ACCEL, max_params['accel'] * ratio)
        decel = max(MIN_DECEL, max_params['decel'] * ratio)
        speeds[node_id] = {
            'target_pos': target_positions[node_id],
            'vel': vel,
            'accel': accel,
            'decel': decel
        }
    return speeds

def run_joint_sequence(bus, sequence):
    for step_idx, joint_angles in enumerate(sequence):
        print(f"\n[#{step_idx+1}] 목표 위치로 이동 중...")
        speeds = calculate_normalized_speeds(bus, joint_angles)

        for node_id, params in speeds.items():
            send_traj_vel_limit(bus, node_id, params['vel'])
            send_traj_accel_limits(bus, node_id, params['accel'], params['decel'])
            send_input_pos(bus, node_id, params['target_pos'])

        time.sleep(1.5)

        for node_id, params in speeds.items():
            wait_until_reached(bus, node_id, params['target_pos'], tolerance=TOLERANCE)
        print("[완료] 모든 노드 목표 도달")
        print("[수분 시작] 5초 대기")
        time.sleep(5)

def process_joint_set(bus, joint_angles):
    print(f"\n[단일] 목표 위치로 이동 중...")
    speeds = calculate_normalized_speeds(bus, joint_angles)

    for node_id, params in speeds.items():
        send_traj_vel_limit(bus, node_id, params['vel'])
        send_traj_accel_limits(bus, node_id, params['accel'], params['decel'])
        send_input_pos(bus, node_id, params['target_pos'])

    time.sleep(1.5)

    for node_id, params in speeds.items():
        wait_until_reached(bus, node_id, params['target_pos'], tolerance=TOLERANCE)

    print("[완료] 모든 노드 목표 도달")
    #print("[수분 시작] 5초 대기")
    #time.sleep(5)

'''
# Main
try:
    bus = can.interface.Bus(interface='slcan', channel=CHANNEL, bitrate=BITRATE)
    print("[INFO] CAN 버스 연결 성공")
except Exception as e:
    print(f"[ERROR] CAN 버스 초기화 실패: {e}")
    sys.exit(1)

initialize_nodes(bus, [0, 1, 2, 3, 4, 5])
run_joint_sequence(bus, JOINT_SEQUENCE)
'''
