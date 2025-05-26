import json
import numpy as np

def load_detected_objects_test(file_path="detected_objects.json"):
    with open(file_path, "r") as f:
        detected_objects = json.load(f)
    return detected_objects

def print_detected_objects_test(detected_objects):
    if not detected_objects['detected_objects']:  # 리스트가 비어있는 경우
        print("🔍 검출된 대상이 없습니다.")
        return
    
    if 'detected_objects' in detected_objects:
        for obj in detected_objects['detected_objects']:
            print(f"index : {obj['index']}, X : {obj['X']}, Y : {obj['Y']}, Z : {obj['Z']}")
    else:
        print("⚠️ 오류: detected_objects 키가 없습니다.")

# 값 변환은 로봇팔 베이스로부터 카메라의 축 변환으로 생각할 것
def euler_to_dcm_deg(roll_deg, pitch_deg, yaw_deg): 
    roll = np.deg2rad(roll_deg)
    pitch = np.deg2rad(pitch_deg)
    yaw = np.deg2rad(yaw_deg)

    # 각 회전 축에 대한 회전 행렬 생성
    Rz = np.array([
        [np.cos(yaw), -np.sin(yaw), 0],
        [np.sin(yaw), np.cos(yaw), 0],
        [0, 0, 1]
    ])
    Ry = np.array([
        [np.cos(pitch), 0, np.sin(pitch)],
        [0, 1, 0],
        [-np.sin(pitch), 0, np.cos(pitch)]
    ])
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(roll), -np.sin(roll)],
        [0, np.sin(roll), np.cos(roll)]
    ])

    # 회전 행렬 계산: Rz @ Ry @ Rx
    return Rz @ Ry @ Rx

'''
def transform_coordinates60(
    file_path="detected_objects.json",
    roll_deg=-90, pitch_deg=0, yaw_deg=90,
    tx=0.0, ty=0.0, tz=0.0
):
    with open(file_path, "r") as f:
        data = json.load(f)

    # 회전행렬과 이동 벡터 계산
    R = euler_to_dcm_deg(roll_deg, pitch_deg, yaw_deg)
    T = np.array([tx, ty, tz])

    transformed = []
    for obj in data["detected_objects"]:

        # 픽셀 좌표를 미터로 변환 (기존 로직)
        x = (obj["X"] - 472) / 1000  # 100 픽셀은 10cm를 의미 즉 '100'을 0.1로 변환 해야 함
        y = -(obj["Y"] - 406) / 1000
        z = -0.5 # 단위 10은 10cm를 의미 즉'10'을 0.1로 변환해야 함

        
        P_cam = np.array([x, y, z])

        # 회전 및 이동 변환
        P_base = R @ P_cam + T

        # 변환된 객체 정보를 저장
        transformed.append({
            "index": obj["index"],
            "X": P_base[0],
            "Y": P_base[1],
            "Z": P_base[2]
        })

    # 결과를 원본 데이터에 덮어쓰기
    data["detected_objects"] = transformed
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

    return transformed
'''

def transform_coordinates60(
    file_path="detected_objects.json",
    tx=0.0, ty=0.0, tz=0.0
):
    with open(file_path, "r") as f:
        data = json.load(f)

    # 직접 지정된 회전 행렬: (x, y, z) → (z, -x, y)
    R = np.array([
        [0, 0, 1],
        [-1, 0, 0],
        [0, 1, 0]
    ])
    T = np.array([tx, ty, tz])

    transformed = []
    for obj in data["detected_objects"]:
        # 픽셀 → 미터 단위로 변환
        x = (obj["X"] - 472) / 1000
        y = -(obj["Y"] - 406) / 1000
        z = 0.5  # 고정된 깊이값

        P_cam = np.array([x, y, z])
        P_base = R @ P_cam + T

        transformed.append({
            "index": obj["index"],
            "X": P_base[0],
            "Y": P_base[1],
            "Z": P_base[2]
        })

    data["detected_objects"] = transformed
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

    return transformed

# 테스트용 메인 함수
if __name__ == "__main__":
    # 원본 객체 출력
    print("📦 원본 좌표:")
    detected_objects = load_detected_objects_test("detected_test.json")
    print_detected_objects_test(detected_objects)

    print("\n🔄 좌표 변환 후:")
    transformed_objects = transform_coordinates60("detected_objects.json", tx=0.2, ty=0.1, tz=0.0)
    print_detected_objects_test({"detected_objects": transformed_objects})
