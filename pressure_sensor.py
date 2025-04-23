# -*- coding: utf-8 -*-
import utime
import math # 고도 계산용 pow
import config
# bmp280 라이브러리 및 필요한 상수 임포트
from bmp280 import BMP280, BMP280_OS_STANDARD, BMP280_IIR_FILTER_4

# 모듈 전역 변수
_i2c = None
_log_func = None
_bmp_sensor = None # 실제 BMP280 라이브러리 객체
is_initialized = False

def _log(message):
    if _log_func: _log_func(f"[PressureSensor] {message}")
    else: print(f"[PressureSensor] {message}")

def init(i2c_bus, log_callback=None):
    """BMP280 센서 초기화, FLOOR 케이스 설정 적용 및 Sleep 모드 설정"""
    global _i2c, _log_func, _bmp_sensor, is_initialized
    _i2c = i2c_bus
    _log_func = log_callback
    is_initialized = False
    try:
        # --- 실제 BMP280 라이브러리 객체 생성 (use_case=None 으로 기본 설정 방지) ---
        _bmp_sensor = BMP280(i2c_bus, addr=config.BMP280_ADDR, use_case=None)
        # --------------------------------------------------------------------

        # --- 'BMP280_CASE_FLOOR'에 해당하는 설정 적용 ---
        # Floor case: OS_STANDARD (Press=x4, Temp=x1), IIR Filter=4
        _bmp_sensor.oversample(BMP280_OS_STANDARD) # Standard 오버샘플링 설정 (Press=x4, Temp=x1)
        _bmp_sensor.iir = BMP280_IIR_FILTER_4      # IIR 필터 4 설정
        _log(f"BMP280 설정: Oversampling=Standard(x4/x1), IIR Filter=4")
        # -------------------------------------------

        # 초기 상태를 Sleep 모드로 설정
        _bmp_sensor.sleep() # 메소드 호출로 수정
        _log("BMP280 초기화 및 Sleep 모드 진입 완료")
        is_initialized = True
        return True
    except Exception as e:
        _log(f"BMP280 초기화 중 오류: {e}")
        return False

def get_pressure_reading(num_samples=config.PRESSURE_AVG_SAMPLES):
    """Forced 모드로 전환, 설정된 오버샘플링/필터로 여러 번 측정 후 평균 압력 반환 (Pa), 끝나고 Sleep"""
    if not is_initialized or _bmp_sensor is None:
        _log("BMP280이 초기화되지 않았습니다.")
        return None

    readings = []
    # --- 측정 전 현재 파워 모드 확인 (선택적 디버깅) ---
    # try:
    #     current_power = _bmp_sensor.power_mode
    #     if current_power != BMP280_POWER_SLEEP:
    #          _log(f"경고: 측정 시작 전 Sleep 모드가 아님 (현재: {current_power})")
    # except Exception as e:
    #     _log(f"파워 모드 확인 오류: {e}")
    # ----------------------------------------------

    try:
        # --- 측정 대기 시간 결정 ---
        # oversample() 메소드가 read_wait_ms를 설정하므로 이를 사용
        wait_time = _bmp_sensor.read_wait_ms if hasattr(_bmp_sensor, 'read_wait_ms') and _bmp_sensor.read_wait_ms > 0 else 20 # 안전 기본값
        _log(f"측정 대기 시간: {wait_time} ms (Standard Oversampling 기준)")
        # ---------------------------

        for i in range(num_samples):
            _bmp_sensor.force_measure() # Forced 모드 시작 (power_mode 속성 사용)
            utime.sleep_ms(wait_time)   # 계산된/설정된 대기 시간 사용

            # --- 온도 보상된 압력 값 읽기 (속성 접근) ---
            pressure = _bmp_sensor.pressure # 속성 접근으로 수정
            # ---------------------------------------

            if pressure is not None:
                 readings.append(pressure)
                 # 디버깅 로그 추가 가능
                 # _log(f" 샘플 {i+1}: {pressure:.2f} Pa")
            else:
                 _log(f" 샘플 {i+1}: 압력 읽기 실패")

            # 연속 측정 시 약간의 간격 (필요에 따라)
            if i < num_samples - 1:
                 utime.sleep_ms(50) # 예: 50ms

        if not readings:
            _log("유효한 압력 값을 읽지 못했습니다.")
            # 최종적으로 Sleep 모드 전환 시도
            _bmp_sensor.sleep() # 메소드 호출로 수정
            return None

        # 평균값 계산
        avg_pressure = sum(readings) / len(readings)
        _log(f"평균 압력 측정: {avg_pressure:.2f} Pa ({len(readings)}/{num_samples} 샘플)")
        # 최종적으로 Sleep 모드 전환
        _bmp_sensor.sleep() # 메소드 호출로 수정
        return avg_pressure

    except Exception as e:
        _log(f"압력 측정 중 오류: {e}")
        # 오류 발생 시에도 Sleep 모드 시도
        try:
            _bmp_sensor.sleep() # 메소드 호출로 수정
        except Exception as se:
             _log(f"Sleep 모드 전환 오류: {se}")
        return None

def pressure_to_altitude(pressure_pa, sea_level_pa=config.SEA_LEVEL_PRESSURE_PA):
    """기압(Pa)을 고도(m)로 변환 (표준 대기 모델 근사)"""
    # 고도(m) = 44330 * (1 - (P/P0)^(1/5.257))
    if pressure_pa is None or pressure_pa <= 0:
        return None
    try:
        # pow 계산 시 부동소수점 사용 명시
        pressure_ratio = float(pressure_pa) / float(sea_level_pa)
        altitude = 44330.0 * (1.0 - math.pow(pressure_ratio, 1.0/5.257))
        return altitude
    except Exception as e:
        _log(f"고도 변환 중 오류: {e}")
        return None