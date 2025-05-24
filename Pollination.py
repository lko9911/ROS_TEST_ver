import asyncio
import websockets
from gpiozero import PWMOutputDevice, DigitalOutputDevice

# ───── 모터 제어 설정 ─────
IN1 = DigitalOutputDevice(17)
IN2 = DigitalOutputDevice(27)
ENA = PWMOutputDevice(13, frequency=1000)

# ───── 모터 작동 함수 ─────
async def run_motor(duration=5, power=0.8):
    print(f"💧 수분 펌프 작동: {duration}초 (출력: {int(power * 100)}%)")
    IN1.on()
    IN2.off()
    ENA.value = power
    await asyncio.sleep(duration)
    ENA.off()
    IN1.off()
    IN2.off()
    print("💧 수분 펌프 정지 완료")

# ───── WebSocket 핸들러 ─────
async def handler(websocket):
    async for message in websocket:
        print(f"📨 수신 메시지: {message}")

        if message == "DONE":
            response = "🟢 작업 완료 확인 및 모터 실행"
            await websocket.send(response)
            await run_motor(duration=10, power=0.75)
        else:
            response = f"⚠️ 알 수 없는 메시지: {message}"
            await websocket.send(response)

# ───── WebSocket 서버 실행 ─────
async def main():
    HOST = "0.0.0.0"
    PORT = 8767
    print(f"🛰️ WebSocket 서버 실행 중... (포트: {PORT})")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # 서버 유지

if __name__ == "__main__":
    asyncio.run(main())
