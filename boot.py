import machine

is_dev_mode = False
try:
    # usb_cdc는 Pico/Pico W의 내장 모듈입니다.
    # PC의 IDE는 이 모듈을 알지 못해 오류로 표시할 수 있지만, 실제 기기에서는 정상 동작합니다.
    # try...except로 감싸 IDE의 오류 표시를 막고, 보다 안정적인 코드를 만듭니다.
    import usb_cdc

    # usb_cdc.data 객체의 존재 여부로 터미널 연결을 확인하는 것이 더 안정적입니다.
    # 터미널이 연결되지 않으면 usb_cdc.data는 None이 됩니다.
    if usb_cdc.data:
        is_dev_mode = True
except ImportError:
    # usb_cdc 모듈이 없는 보드이거나, IDE에서 정적 분석을 하는 경우 오류 없이 통과합니다.
    pass

# USB 데이터 통신(터미널) 연결 여부에 따른 분기
if is_dev_mode:
    print("USB 데이터 연결됨 - 개발 모드 (자동 실행 건너뜀)")
else:
    print("데이터 연결 없음 - 자동 실행 모드")
    try:
        import app_only_bmp388
        app_only_bmp388.main()
    except Exception as e:
        print(f"자동 실행 실패: {e}")
