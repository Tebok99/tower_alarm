# -*- coding: utf-8 -*-
import machine
import utime
import audio_player
import config
import motion_sensor
import pressure_sensor

# --- 전역 변수 ---
led = None
i2c0 = None  # LSM6DS3용
i2c1 = None  # BMP280용

current_state = config.STATE_INIT
last_log_ticks = 0
low_batt_warning_active = False

# --- 유틸리티 함수 (log_event, init_led, set_led_state) ---
def log_event(event):
    global last_log_ticks
    try:
        current_ticks = utime.ticks_us()
        if last_log_ticks == 0:
            relative_time_ms = 0
        else:
            relative_time_ms = utime.ticks_diff(current_ticks, last_log_ticks) // 1000
        last_log_ticks = current_ticks
        log_entry = f"[{relative_time_ms}ms] | {event}\n"
        print(log_entry, end="")
        try:
            with open(config.LOG_FILE_NAME, "a") as file:
                file.write(log_entry)
        except Exception as fe:
            print(f"로그 파일 작성 실패: {fe}")
    except Exception as e:
        print(f"로그 파일 기록 실패: {e}")

def init_led():
    global led
    led = machine.Pin(config.PIN_LED, machine.Pin.OUT)
    led.off()

def set_led_state(state):
    global led
    if state == config.STATE_ERROR:
        led.off()
    elif state == config.STATE_IDLE:
        led.off()  # IDLE 상태는 LED OFF (저전력)
    elif state == config.STATE_MONITORING_PRESSURE:
        led.on()  # 모니터링 중 LED ON
    elif state == config.STATE_ACTION:
        led.on()  # 재생 중 LED ON
    else:
        led.off()

def cleanup_and_exit(reason="프로그램 종료"):
    """리소스 정리 및 프로그램 종료 처리"""
    global i2c0, i2c1, led
    log_event(f"{reason} - 종료 처리 시작")
    # 모든 활성 작업 중단
    # 현재 실행 중인 센서 읽기 중단
    machine.lightsleep(100)  # 진행 중인 작업 완료 대기

    # I2C 버스 해제
    if i2c0:
        try:
            i2c0 = None
            log_event("I2C0 해제 완료")
        except Exception as e:
            log_event(f"I2C0 해제 중 오류: {e}")

    if i2c1:
        try:
            i2c1 = None
            log_event("I2C1 해제 완료")
        except Exception as e:
            log_event(f"I2C1 해제 중 오류: {e}")

    # LED 끄기
    if led:
        try:
            led.off()
            log_event("LED 해제 완료")
        except Exception as e:
            log_event(f"LED 해제 중 오류: {e}")

    log_event("리소스 정리 완료.")

    # 짧은 대기 후 종료
    utime.sleep_ms(500)
    log_event("프로그램 정상 종료")
    return

def init_sensors_with_retry():
    """센서 및 오디오 초기화 (재시도 포함)"""
    for attempt in range(config.SENSOR_INIT_MAX_RETRIES):
        log_event(f"센서 초기화 시도 {attempt + 1}/{config.SENSOR_INIT_MAX_RETRIES}")

        success_count = 0
        total_components = 3  # LSM6DS3, BMP280, Audio Player

        # LSM6DS3 초기화
        try:
            if motion_sensor.init(i2c0, log_event):
                log_event("LSM6DS3 초기화 성공")
                success_count += 1
            else:
                log_event("LSM6DS3 초기화 실패")
        except Exception as e:
            log_event(f"LSM6DS3 초기화 중 예외: {e}")

        # BMP280 초기화
        try:
            if pressure_sensor.init(i2c1, log_event):
                log_event("BMP280 초기화 성공")
                success_count += 1
            else:
                log_event("BMP280 초기화 실패")
        except Exception as e:
            log_event(f"BMP280 초기화 중 예외: {e}")

        # Audio Player 초기화 추가
        try:
            if audio_player.init(log_event):
                log_event("I2S Audio Player 초기화 성공")
                success_count += 1
            else:
                log_event("I2S Audio Player 초기화 실패")
        except Exception as e:
            log_event(f"I2S Audio Player 초기화 중 예외: {e}")

        if success_count == total_components:
            log_event("모든 구성 요소 초기화 성공")
            return True
        else:
            log_event(f"초기화 성공: {success_count}/{total_components}")
            if attempt < config.SENSOR_INIT_MAX_RETRIES - 1:
                log_event(f"{config.SENSOR_INIT_RETRY_DELAY_MS}ms 후 재시도...")
                utime.sleep_ms(config.SENSOR_INIT_RETRY_DELAY_MS)

    log_event("센서 및 오디오 초기화 최종 실패")
    return False

# --- 메인 실행 로직 ---
def main():
    global current_state, last_log_ticks, i2c0, i2c1, led

    last_log_ticks = utime.ticks_us()
    log_event("시스템 시작")
    init_led()
    current_state = config.STATE_INIT

    # I2C 버스 초기화
    try:
        i2c0 = machine.I2C(config.I2C0_BUS_ID, scl=machine.Pin(config.PIN_I2C0_SCL),
                           sda=machine.Pin(config.PIN_I2C0_SDA), freq=config.I2C0_FREQ)
        i2c1 = machine.SoftI2C(scl=machine.Pin(config.PIN_I2C1_SCL), sda=machine.Pin(config.PIN_I2C1_SDA),
                               freq=config.I2C1_FREQ)  # I2C 설정 오류로 SoftI2C를 설정함. 이유 모름..
        log_event("I2C 버스 초기화 완료 (Bus 0, Bus 1)")
    except Exception as e:
        log_event(f"I2C 버스 초기화 실패: {e}")
        current_state = config.STATE_ERROR
        set_led_state(config.STATE_ERROR)
        cleanup_and_exit("I2C 버스 초기화 실패")
        return

    # 센서 초기화 (재시도 포함)
    if not init_sensors_with_retry():
        log_event("센서 초기화 최종 실패")
        current_state = config.STATE_ERROR
        set_led_state(config.STATE_ERROR)
        cleanup_and_exit("센서 초기화 실패")
        return

    log_event("모든 센서 초기화 완료. 메인 루프 시작.")
    current_state = config.STATE_IDLE
    set_led_state(current_state)

    initial_altitude = None
    pressure_monitor_start_time = None
    last_pressure_check_time = None

    try:
        while True:
            current_time_ms = utime.ticks_ms()

            # --- 상태별 처리 ---
            if current_state == config.STATE_IDLE:
                is_triggered = motion_sensor.check_for_movement()
                if is_triggered:
                    log_event("움직임 감지 -> 기압 모니터링 시작")
                    # 초기 기압 및 고도 측정
                    initial_pressure = pressure_sensor.get_pressure_reading()
                    if initial_pressure is not None:
                        initial_altitude = pressure_sensor.pressure_to_altitude(initial_pressure)
                        if initial_altitude is not None:
                            log_event(f"초기 고도 설정: {initial_altitude:.2f} m (P={initial_pressure:.1f} Pa)")
                            current_state = config.STATE_MONITORING_PRESSURE
                            set_led_state(current_state)
                            pressure_monitor_start_time = last_pressure_check_time = current_time_ms
                        else:
                            log_event("초기 고도 계산 실패")
                            # 상태는 IDLE 유지
                    else:
                        log_event("초기 기압 측정 실패")
                        # 상태는 IDLE 유지
                else:
                    # 가속도 미감지 시 저전력 Sleep
                    machine.lightsleep(config.IDLE_SLEEP_MS)

            elif current_state == config.STATE_MONITORING_PRESSURE:
                # 모니터링 간격 확인
                if utime.ticks_diff(current_time_ms, last_pressure_check_time) >= config.PRESSURE_MONITOR_INTERVAL_MS:
                    # 기압 측정 및 고도 변화 확인
                    current_pressure = pressure_sensor.get_pressure_reading()
                    if current_pressure is not None and initial_altitude is not None:
                        current_altitude = pressure_sensor.pressure_to_altitude(current_pressure)
                        if current_altitude is not None:
                            last_pressure_check_time = current_time_ms
                            altitude_change = abs(current_altitude - initial_altitude)
                            log_event(
                                f"고도 변화 모니터링: 현재={current_altitude:.2f}m, 초기={initial_altitude:.2f}m, 변화량={altitude_change:.2f}m")

                            # 고도 변화 임계값 확인
                            if altitude_change >= config.ALTITUDE_CHANGE_THRESHOLD:
                                log_event(f"고도 변화 임계값 ({config.ALTITUDE_CHANGE_THRESHOLD}m) 도달! 음원 재생.")
                                # 재생 전 상태를 ACTION으로 변경하고 LED 켬 (선택사항)
                                current_state = config.STATE_ACTION
                                set_led_state(current_state)  # 재생 중 LED
                                audio_player.play_wav_with_validation()
                                # 재생 후 다시 모니터링 상태 유지 및 LED 업데이트
                                current_state = config.STATE_MONITORING_PRESSURE
                                set_led_state(current_state)
                                # 임계 고도값 변화 시점의 고도값과, 기압 측정 시작 시간 초기값 설정
                                initial_altitude = current_altitude
                                pressure_monitor_start_time = current_time_ms
                        else:  # 고도 계산 실패
                            log_event("현재 고도 계산 실패")
                    else:  # 기압 측정 실패 또는 초기 고도 없음
                        log_event("현재 기압 측정 실패 또는 초기 고도 없음")

                # 모니터링 타임아웃 확인
                if utime.ticks_diff(current_time_ms, pressure_monitor_start_time) > config.PRESSURE_MONITOR_TIMEOUT_MS:
                    log_event("기압 모니터링 타임아웃. IDLE 상태로 복귀.")
                    current_state = config.STATE_IDLE
                    set_led_state(current_state)

            elif current_state == config.STATE_ACTION:
                # 오디오 재생은 블로킹되므로, 이 상태에 오래 머물지 않음
                # 혹시 모를 경우를 대비해 IDLE로 돌리는 로직 추가 가능
                log_event("ACTION 상태 오류? IDLE로 강제 전환")
                current_state = config.STATE_IDLE
                set_led_state(current_state)
                utime.sleep_ms(100)

    except KeyboardInterrupt:
        log_event("Ctrl+C 감지 - 정상 종료 시작")
        cleanup_and_exit("사용자 요청으로 인한 프로그램 종료")
    except Exception as e:
        log_event(f"메인 루프 오류 발생: {e}")
        current_state = config.STATE_ERROR
        set_led_state(config.STATE_ERROR)
        cleanup_and_exit("메인 루프 오류로 인한 프로그램 종료")
    finally:
        # 최종 정리
        log_event("프로그램 최종 종료")

if __name__ == "__main__":
    main()