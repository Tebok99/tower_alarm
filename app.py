def initialize_bmp388():
    """BMP388 센서 초기화"""
    global base_altitude

    try:
        # I2C 통신 시작
        i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)

        # 사용 가능한 I2C 장치 스캔
        devices = i2c.scan()
        if not devices:
            print("I2C 장치를 찾을 수 없습니다!")
            return False

        print(f"I2C 장치 발견: {[hex(d) for d in devices]}")

        # BMP388 센서 객체 생성
        bmp = BMP388(i2c)

        # 기준 고도 설정 (10회 측정 평균)
        altitude_sum = 0.0
        for i in range(10):
            altitude_sum += bmp.read_altitude(SEALEVELPRESSURE_HPA)
            time.sleep_ms(100)

        base_altitude = altitude_sum / 10.0

        print(f"기준 고도 설정 완료: {base_altitude:.2f} m")
        return bmp

    except Exception as e:
        print(f"센서 초기화 오류: {e}")
        return False

def measure_altitude(bmp):
    """고도 측정"""
    global current_altitude, altitude_difference

    try:
        current_altitude = bmp.read_altitude(SEALEVELPRESSURE_HPA)
        altitude_difference = current_altitude - base_altitude

        # 디버그 출력
        print(f"현재 고도: {current_altitude:.2f} m, 변화량: {altitude_difference:.2f} m")
        return True

    except Exception as e:
        print(f"측정 오류: {e}")
        return False

def main():
    """메인 프로그램"""
    global last_measurement_time, sound_start_time, is_playing_sound, sensor_initialized

    # 핀 초기화
    status_led = StatusLED(LED_PIN)

    # 초기화 표시
    status_led.on()
    print("Tower Alarm System 시작")

    # 객체 생성
    logger = Logger()
    power_manager = PowerManager(34)  # ADC 핀 사용 예시

    # 센서 초기화
    bmp = initialize_bmp388()
    sensor_initialized = bool(bmp)

    if sensor_initialized:
        status_led.off()
        print("시스템 초기화 완료")

        # 초기화 성공 표시
        status_led.blink(count=2, interval=300)
    else:
        print("초기화 실패 - 센서 연결 확인 필요")
        # 오류 표시
        status_led.blink(count=5, interval=100)

    last_measurement_time = time.ticks_ms()

    try:
        while True:
            current_time = time.ticks_ms()

            # 전원 모드 처리
            power_manager.handle_power_mode()

            # 소리 재생 중이면 고도 측정 건너뛰기
            if is_playing_sound:
                if time.ticks_diff(current_time, sound_start_time) < SOUND_DURATION:
                    # 알람 상태 표시 (LED 깜빡임)
                    if time.ticks_diff(current_time, sound_start_time) % 1000 < 500:
                        status_led.on()
                    else:
                        status_led.off()
                else:
                    # 알람 종료
                    is_playing_sound = False
                    status_led.off()
                    print("알람 종료")
                continue

            # 센서가 초기화되지 않은 경우 재시도
            if not sensor_initialized:
                if time.ticks_diff(current_time, last_measurement_time) > 5000:  # 5초마다 재시도
                    bmp = initialize_bmp388()
                    sensor_initialized = bool(bmp)
                    last_measurement_time = current_time
                continue

            # 측정 주기 확인 (1초 또는 그 이하)
            if time.ticks_diff(current_time, last_measurement_time) >= MEASUREMENT_INTERVAL:
                if measure_altitude(bmp):
                    # 로그 기록
                    temperature = bmp.read_temperature()
                    pressure = bmp.read_pressure() / 100.0  # Pa -> hPa
                    logger.log_data(temperature, pressure, current_altitude, altitude_difference)

                    # 1미터 이상 변화 감지
                    if abs(altitude_difference) >= ALTITUDE_THRESHOLD:
                        print("*** 고도 변화 감지! 알람 시작 ***")
                        is_playing_sound = True
                        sound_start_time = current_time
                        status_led.on()  # 알람 시작 표시

                last_measurement_time = current_time

            # 짧은 지연
            time.sleep_ms(10)

    except KeyboardInterrupt:
        # 프로그램 종료 시 정리
        status_led.off()
        print("프로그램 종료")

if __name__ == "__main__":
    main()