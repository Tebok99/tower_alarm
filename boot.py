# boot.py - VBUS 핀을 사용한 USB 전원 감지
import machine
import sys

def is_usb_powered():
    try:
        # Raspberry Pi Pico의 VBUS 감지 핀 사용
        # 다른 보드의 경우 해당 핀 번호로 수정 필요
        vbus_sense = machine.Pin(24, machine.Pin.IN)
        return vbus_sense.value() == 1
    except:
        # VBUS 핀이 없는 경우 대체 방법
        try:
            return hasattr(sys.stdin, 'read') and sys.stdin.read(0) is not None
        except:
            return False

# 전원 공급원에 따른 분기
if is_usb_powered():
    print("USB 전원 감지 - 개발 모드")
    # USB 전원 시에는 app.py를 자동 실행하지 않음
else:
    print("외부 배터리 전원 - 자동 실행 모드")
    # 외부 전원 시에만 app.py 자동 실행
    exec(open('app.py').read())