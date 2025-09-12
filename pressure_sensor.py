# -*- coding: utf-8 -*-
import utime
import config
# bmp280 라이브러리 및 필요한 상수 임포트
from bmp280 import BMP280, BMP280_OS_STANDARD, BMP280_IIR_FILTER_4

# 모듈 전역 변수
_log_func = None
_bmp_sensor = None  # 실제 BMP280 라이브러리 객체
is_initialized = False

def _log(message):
    global _log_func
    if _log_func:
        _log_func(f"[PressureSensor] {message}")
    else:
        print(f"[PressureSensor] {message}")

def init(i2c_bus, log_callback=None):
    """BMP280 센서 초기화, FLOOR 케이스 설정 적용 및 Sleep 모드 설정"""
    global _log_func, _bmp_sensor, is_initialized
    _log_func = log_callback
    is_initialized = False
    try:
        # --- 실제 BMP280 라이브러리 객체 생성 (use_case=None 으로 기본 설정 방지) ---
        _bmp_sensor = BMP280(i2c_bus, addr=config.BMP280_ADDR, use_case=None)
        # --------------------------------------------------------------------

        # --- 'BMP280_CASE_FLOOR'에 해당하는 설정 적용 ---
        # Floor case: OS_STANDARD (Temp=x1, Press=x4), IIR Filter=4
        _bmp_sensor.iir = BMP280_IIR_FILTER_4
        _bmp_sensor.oversample(BMP280_OS_STANDARD)
        _log(f"BMP280 설정: Oversampling=Standard(x4/x1), IIR Filter=4")

        _bmp_sensor.force_measure()
        _log("BMP280 초기화 및 OSR, IIR, Forced Mode 명령 후 Sleep 모드 진입 완료")
        is_initialized = True
        return True
    except Exception as e:
        _log(f"BMP280 초기화 중 오류: {e}")
        return False

def get_pressure_reading():
    """Forced 모드로 전환, Status 레지스터를 확인하여 측정 완료 후 압력 반환 (Pa), ㅇ정상 종료시 Sleep 모드 전환하나 실행 실패 시 Sleep 모드 전환 실행"""
    if not is_initialized:
        _log("BMP280이 초기화 안 되었습니다.")
        return None
    try:
        # --- 측정 대기 시간 결정 (최대 대기 시간 설정) ---
        wait_time = _bmp_sensor.read_wait_ms if _bmp_sensor.read_wait_ms > 0 else 30  # 안전 기본값 ms
        _log(f"최대 측정 대기 시간: {wait_time} ms (Standard Oversampling 기준)")

        # Forced 모드 시작
        _bmp_sensor.force_measure()

        # Status 레지스터를 폴링하여 측정 완료 대기
        start_time = utime.ticks_ms()
        timeout = 500  # ms

        utime.sleep_ms(wait_time)  # 기본 대기 시간

        while _bmp_sensor.is_measuring:
            current_time = utime.ticks_ms()
            if utime.ticks_diff(current_time, start_time) > timeout:
                _log(f"측정 대기 타임아웃 도달({timeout} ms)")
                break
            utime.sleep_ms(2)  # 2ms 간격 폴링

        actual_wait_time = utime.ticks_diff(utime.ticks_ms(), start_time)
        _log(f"측정 실제 대기 시간: {actual_wait_time} ms")

        # --- 온도 보상된 압력 값 읽기 (속성 접근) ---
        pressure = _bmp_sensor.pressure

        if pressure is None:
            _log("압력 읽기 실패")
            _bmp_sensor.sleep()
            _log(f"Sleep 모드 전환 오류: {se}")
            return None
        _log(f"압력 값: {pressure:.2f} Pa")
        return pressure

    except Exception as e:
        _log(f"압력 측정 중 오류: {e}")
        # 오류 발생 시에만 Sleep 모드 시도
        try:
            _bmp_sensor.sleep()
        except Exception as se:
            _log(f"Sleep 모드 전환 오류: {se}")
        return None


def pressure_to_altitude(pressure_pa, sea_level_pa=config.SEA_LEVEL_PRESSURE_PA):
    """기압(Pa)을 고도(m)로 변환 (표준 대기 모델 근사)"""
    # 고도(m) = 44330 * (1 - (P/P0)^(1/5.255))
    if pressure_pa is None or pressure_pa <= 0:
        return None
    try:
        pressure_ratio = float(pressure_pa) / float(sea_level_pa)
        altitude = 44330.0 * (1.0 - pressure_ratio ** (1.0 / 5.255))
        return altitude
    except Exception as e:
        _log(f"고도 변환 중 오류: {e}")
        return None