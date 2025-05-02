# -*- coding: utf-8 -*-
import machine
import utime
import config
import motion_sensor
import pressure_sensor # 기압 센서 모듈 추가
import audio_player

# --- 전역 변수 ---
led = machine.Pin(config.PIN_LED, machine.Pin.OUT)
adc = machine.ADC(config.PIN_ADC_VSYS)
i2c0 = None # LSM6DS3용
i2c1 = None # BMP280용

current_state = config.STATE_INIT
last_log_ticks = 0
low_batt_warning_active = False

# --- 유틸리티 함수 (log_event, init_led, set_led_state, check_voltage, check_low_battery) ---
def log_event(event):
    global last_log_ticks
    try:
        voltage = check_voltage()
        current_ticks = utime.ticks_us()
        if last_log_ticks == 0: relative_time_ms = 0
        else: relative_time_ms = utime.ticks_diff(current_ticks, last_log_ticks) // 1000
        last_log_ticks = current_ticks
        log_entry = f"[{relative_time_ms}ms],[{voltage:.2f}V] | {event}\n"
        print(log_entry, end="")
        try:
            with open(config.LOG_FILE_NAME, "a") as file: file.write(log_entry)
        except Exception as fe: print(f"로그 파일 작성 실패: {fe}")
    except Exception as e: print(f"로그 파일 기록 실패: {e}")

def init_led(): led.off()

def set_led_state(state):
    if state == config.STATE_ERROR: led.off()
    elif state == config.STATE_IDLE: led.off() # IDLE 상태는 LED OFF (저전력)
    elif state == config.STATE_MONITORING_PRESSURE: led.on() # 모니터링 중 LED ON
    elif state == config.STATE_ACTION: led.on() # 재생 중 LED ON
    else: led.off()

def check_voltage():
    try:
        adc_value = adc.read_u16(); return adc_value * config.ADC_REF_VOLTAGE / 65535 * config.VOLTAGE_DIVIDER_RATIO
    except Exception: return 0.0

def check_low_battery():
    global low_batt_warning_active
    voltage = check_voltage()
    low_now = voltage > 0 and voltage < config.LOW_BATT_THRESHOLD
    if low_now and not low_batt_warning_active:
        log_event(f"저전력 경고: {voltage:.2f}V"); low_batt_warning_active = True; set_led_state(config.STATE_LOW_BATT)
    elif not low_now and low_batt_warning_active:
        log_event(f"저전력 상태 해제: {voltage:.2f}V"); low_batt_warning_active = False; set_led_state(current_state)
    return low_now

# --- 메인 실행 로직 ---
def main():
    global current_state, last_log_ticks, i2c0, i2c1

    last_log_ticks = utime.ticks_us()
    log_event("시스템 시작")
    init_led()
    current_state = config.STATE_INIT

    # I2C 버스 초기화
    try:
        i2c0 = machine.I2C(config.I2C0_BUS_ID, scl=machine.Pin(config.PIN_I2C0_SCL), sda=machine.Pin(config.PIN_I2C0_SDA), freq=config.I2C0_FREQ)
        i2c1 = machine.SoftI2C(scl=machine.Pin(config.PIN_I2C1_SCL), sda=machine.Pin(config.PIN_I2C1_SDA), freq=config.I2C1_FREQ)   # I2C 설정 오류로 SoftI2C를 설정함. 이유 모름..
        log_event("I2C 버스 초기화 완료 (Bus 0, Bus 1)")
    except Exception as e:
        log_event(f"I2C 버스 초기화 실패: {e}"); current_state = config.STATE_ERROR; set_led_state(config.STATE_ERROR); return

    if check_low_battery(): log_event("초기 전압 낮음.")

    # 센서 초기화
    motion_ok = motion_sensor.init(i2c0, log_event)
    pressure_ok = pressure_sensor.init(i2c1, log_event)

    if not motion_ok or not pressure_ok:
        log_event("센서 초기화 실패. 프로그램 중단."); current_state = config.STATE_ERROR; set_led_state(config.STATE_ERROR)
        while True: utime.sleep(1) # 오류 상태 유지

    log_event("모든 센서 초기화 완료. 메인 루프 시작.")
    current_state = config.STATE_IDLE
    set_led_state(current_state)

    initial_altitude = None
    pressure_monitor_start_time = None
    last_pressure_check_time = None
    last_batt_check_time = utime.ticks_ms()

    while True:
        try:
            current_time_ms = utime.ticks_ms()

            # 배터리 체크
            if utime.ticks_diff(current_time_ms, last_batt_check_time) > 5000:
                check_low_battery()
                last_batt_check_time = current_time_ms

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
                            log_event(f"고도 변화 모니터링: 현재={current_altitude:.2f}m, 초기={initial_altitude:.2f}m, 변화량={altitude_change:.2f}m")

                            # 고도 변화 임계값 확인
                            if altitude_change >= config.ALTITUDE_CHANGE_THRESHOLD:
                                log_event(f"고도 변화 임계값 ({config.ALTITUDE_CHANGE_THRESHOLD}m) 도달! 음원 재생.")
                                # 재생 전 상태를 ACTION으로 변경하고 LED 켬 (선택사항)
                                current_state = config.STATE_ACTION
                                set_led_state(current_state) # 재생 중 LED
                                audio_player.play_wav(log_event)
                                # 재생 후 다시 모니터링 상태 유지 및 LED 업데이트
                                current_state = config.STATE_MONITORING_PRESSURE
                                set_led_state(current_state)
                                # 임계 고도값 변화 시점의 고도값과, 기압 측정 시작 시간 초기값 설정
                                initial_altitude = current_altitude
                                pressure_monitor_start_time = current_time_ms
                        else: # 고도 계산 실패
                            log_event("현재 고도 계산 실패")
                    else: # 기압 측정 실패 또는 초기 고도 없음
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


            # 루프 지연 (Sleep이 없는 경우 대비)
            # 상태별로 필요한 최소 대기시간 고려
            # if current_state != config.STATE_IDLE: # IDLE은 lightsleep 사용
            #     utime.sleep_ms(10) # 짧은 대기

        except KeyboardInterrupt:
            log_event("사용자 요청으로 프로그램 종료")
            break
        except Exception as e:
            log_event(f"메인 루프 오류 발생: {e}")
            current_state = config.STATE_ERROR
            set_led_state(config.STATE_ERROR)
            utime.sleep_ms(1000)

    # --- 종료 처리 ---
    log_event("프로그램 종료 처리 시작")
    if i2c0: 
        try: i2c0.deinit()
        except Exception as e: log_event(f"I2C0 해제 중 오류: {e}")
    if i2c1: 
        try: i2c1.deinit()
        except Exception as e: log_event(f"I2C1 해제 중 오류: {e}")
    led.off()
    log_event("리소스 정리 완료. 프로그램 종료.")


if __name__ == "__main__":
    # 로그 파일 초기화 (선택 사항)
    # try: import os; os.remove(config.LOG_FILE_NAME); log_event("Log Cleared")
    # except OSError: pass
    main()