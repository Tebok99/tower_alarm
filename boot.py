# boot.py - VBUS 핀을 사용한 USB 전원 감지
import usb_cdc

# USB 데이터 통신(터미널) 연결 여부에 따른 분기
# .connected가 True이면 Thonny, PuTTY 등과 연결된 개발 환경으로 간주
if usb_cdc.data.connected:
    print("USB 데이터 연결됨 - 개발 모드 (자동 실행 건너뜀)")
else:
    # 배터리 전원이거나, 데이터 통신 없는 USB 충전기에 연결된 경우
    print("데이터 연결 없음 - 자동 실행 모드")
    try:
        import app_only_bmp388
        app_only_bmp388.main()
    except Exception as e:
        print(f"자동 실행 실패: {e}")
