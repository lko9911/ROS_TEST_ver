import asyncio
import websockets
import json
from functools import partial

'''
8765 : 좌표 전송 포트
8766 : IK 계산 받는 포트
8767 : 로봇팔 동작 완료 포트
'''

raspberrypi_uri_detect = "ws://192.168.33.77:8765"
raspberrypi_uri_done = "ws://192.168.33.77:8767"    

# ───── JSON 로드 함수 ─────
def load_detected_objects(file_path="detected_objects.json"):
    with open(file_path, "r") as f:
        return json.load(f)

# ───── 클라이언트: 좌표 전송 ─────
async def send_detected_objects():
    uri = raspberrypi_uri_detect  # 좌표 받는 쪽
    detected = load_detected_objects()

    if not detected.get("detected_objects"):
        print("🔍 검출된 대상이 없습니다.")
        return

    await asyncio.sleep(1)  # 서버 연결 준비 시간 확보

    async with websockets.connect(uri) as websocket:
        for obj in detected["detected_objects"]:
            data = {
                "X": obj["X"],
                "Y": obj["Y"],
                "Z": obj["Z"]
            }
            await websocket.send(json.dumps(data))
            response = await websocket.recv()
            print(f"[index {obj['index']}] 서버 응답: {response}")

# ───── 클라이언트: 로봇팔 엔드이펙터 완료 정보 전송 ─────
async def send_done_device():
    uri = raspberrypi_uri_done # 서버 URI

    await asyncio.sleep(1)  # 서버 연결 준비 시간 확보

    async with websockets.connect(uri) as websocket:
        done_message = "DONE"
        await websocket.send(done_message)  # 문자열로 완료 전송
        response = await websocket.recv()   # 응답 받기
        print(f"✅ 서버 응답: {response}")


# ───── 서버: 조인트 상태 수신 ─────
async def receive_joint_states(websocket,queue):
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                print("🤖 Joint States Received:", data)
                await queue.put(data)  # 데이터 큐에 넣기
                print(f"✅ 데이터 큐에 넣음: {data}")
            except json.JSONDecodeError:
                print("⚠️ 잘못된 JSON 수신:", message)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"⚠️ WebSocket 연결 종료: {e}")

# ───── 조인트 상태 서버 실행 ─────
async def start_joint_state_server(queue):
 
    server = await websockets.serve(partial(receive_joint_states, queue=queue), "0.0.0.0", 8766)
    print("🟢 조인트 상태 수신 서버 실행 중 (port 8766)...")
    try:
        await server.wait_closed()
    except asyncio.CancelledError:
        print("⚠️ 서버가 정상 종료되었습니다.")

# ───── 통합 실행 ─────
async def main():
    await asyncio.gather(
        start_joint_state_server(),  # 8766 포트에서 조인트 상태 수신
        send_detected_objects()      # 8765로 좌표 전송
    )

if __name__ == "__main__":
    asyncio.run(main())
