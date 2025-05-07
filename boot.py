import usb_cdc
import machine

# USB 연결 여부 확인
if not usb_cdc.data.connected:
    # USB 연결이 아니면 app.py 실행
    machine.main('app.py')
else:
    print("USB connected. Skipping app.py auto-run.")
    # USB 연결 시 app.py 실행을 건너뜁니다.