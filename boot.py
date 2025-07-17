import utime

# 기본적으로 '개발 모드'로 가정하고 시작 (Fail-Safe)
is_dev_mode = True
try:
    import usb_cdc

    # Thonny와 같은 IDE가 USB 시리얼 연결을 설정할 시간을 주기 위해 잠시 대기합니다.
    utime.sleep_ms(1000)

    # 데이터 연결이 없다는 것이 '확실할' 때만 '자동 실행 모드'로 전환합니다.
    if not usb_cdc.data:
        is_dev_mode = False

except ImportError:
    # usb_cdc 모듈 자체가 없는 환경은 데이터 연결을 확인할 수 없으므로
    # '자동 실행 모드'로 간주합니다.
    is_dev_mode = False

if is_dev_mode:
    print("USB 데이터 연결됨 - 개발 모드 (자동 실행 건너뜀)")
else:
    print("데이터 연결 없음 - 자동 실행 모드")
    try:
        import app_only_bmp388_v2
        app_only_bmp388_v2.main()
    except Exception as e:
        print(f"자동 실행 실패: {e}")