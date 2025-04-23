# -*- coding: utf-8 -*-
import utime
import ustruct
import math # 벡터 크기 계산용 sqrt
import config

# 모듈 전역 변수
_i2c = None
_log_func = None
accel_offset = {'x': 0.0, 'y': 0.0, 'z': 0.0}
gravity_estimate = {'x': 0.0, 'y': 0.0, 'z': 0.0}
dynamic_accel = {'x': 0.0, 'y': 0.0, 'z': 0.0}
is_initialized = False

def _log(message):
    if _log_func: _log_func(f"[MotionSensor] {message}")
    else: print(f"[MotionSensor] {message}")

def init(i2c_bus, log_callback=None):
    """센서 초기화 (가속도계만) 및 오프셋 계산"""
    global _i2c, _log_func, is_initialized
    _i2c = i2c_bus; _log_func = log_callback; is_initialized = False
    try:
        devices = _i2c.scan()
        if config.LSM6DS3_ADDR not in devices:
            _log(f"LSM6DS3 센서 감지 실패"); return False
        _i2c.writeto_mem(config.LSM6DS3_ADDR, config.REG_CTRL1_XL, config.ACCEL_ODR_CONFIG)
        utime.sleep_ms(10)
        _i2c.writeto_mem(config.LSM6DS3_ADDR, config.REG_CTRL2_G, config.GYRO_ODR_CONFIG) # 자이로 비활성화
        utime.sleep_ms(100)
        _log("LSM6DS3 레지스터 설정 완료 (Gyro Disabled)")
        if not _calculate_accel_offsets_and_init_filters(): return False
        _log("LSM6DS3 초기화 완료 (Accel Only)"); is_initialized = True; return True
    except Exception as e: _log(f"초기화 중 오류: {e}"); return False

def _read_accel_raw():
    try:
        data = _i2c.readfrom_mem(config.LSM6DS3_ADDR, config.REG_OUTX_L_XL, 6)
        ax = ustruct.unpack('<h', data[0:2])[0]
        ay = ustruct.unpack('<h', data[2:4])[0]
        az = ustruct.unpack('<h', data[4:6])[0]
        return ax, ay, az
    except Exception as e: _log(f"가속도 읽기 오류: {e}"); return 0, 0, 0

def _calculate_accel_offsets_and_init_filters():
    """가속도계 오프셋 계산 및 관련 필터 초기화"""
    global accel_offset, gravity_estimate, dynamic_accel
    _log("가속도 오프셋 계산 시작..."); sum_ax, sum_ay, sum_az = 0, 0, 0
    try:
        for i in range(config.OFFSET_SAMPLE_COUNT):
            ax, ay, az = _read_accel_raw()
            if i > 4 : sum_ax += ax; sum_ay += ay; sum_az += az
            utime.sleep_ms(20)
        num_samples = max(1, config.OFFSET_SAMPLE_COUNT - 5)
        accel_offset['x'] = (sum_ax / num_samples) * config.ACCEL_SENSITIVITY
        accel_offset['y'] = (sum_ay / num_samples) * config.ACCEL_SENSITIVITY
        accel_offset['z'] = (sum_az / num_samples) * config.ACCEL_SENSITIVITY
        _log(f"가속도 오프셋 계산 완료: {accel_offset}")
        ax_raw, ay_raw, az_raw = _read_accel_raw()
        current_ax = ax_raw * config.ACCEL_SENSITIVITY - accel_offset['x']
        current_ay = ay_raw * config.ACCEL_SENSITIVITY - accel_offset['y']
        current_az = az_raw * config.ACCEL_SENSITIVITY - accel_offset['z']
        gravity_estimate['x'] = current_ax; gravity_estimate['y'] = current_ay; gravity_estimate['z'] = current_az
        dynamic_accel['x'] = 0.0; dynamic_accel['y'] = 0.0; dynamic_accel['z'] = 0.0
        _log("초기 필터 값 설정 완료"); return True
    except Exception as e: _log(f"오프셋/필터 초기화 중 오류: {e}"); return False

def _update_dynamic_accel():
    """가속도 값 읽고 중력 제거하여 동적 가속도 계산"""
    global gravity_estimate, dynamic_accel
    ax_raw, ay_raw, az_raw = _read_accel_raw()
    current_ax = ax_raw * config.ACCEL_SENSITIVITY - accel_offset['x']
    current_ay = ay_raw * config.ACCEL_SENSITIVITY - accel_offset['y']
    current_az = az_raw * config.ACCEL_SENSITIVITY - accel_offset['z']
    gravity_estimate['x'] = config.GRAVITY_FILTER_ALPHA * current_ax + (1 - config.GRAVITY_FILTER_ALPHA) * gravity_estimate['x']
    gravity_estimate['y'] = config.GRAVITY_FILTER_ALPHA * current_ay + (1 - config.GRAVITY_FILTER_ALPHA) * gravity_estimate['y']
    gravity_estimate['z'] = config.GRAVITY_FILTER_ALPHA * current_az + (1 - config.GRAVITY_FILTER_ALPHA) * gravity_estimate['z']
    dynamic_accel['x'] = current_ax - gravity_estimate['x']
    dynamic_accel['y'] = current_ay - gravity_estimate['y']
    dynamic_accel['z'] = current_az - gravity_estimate['z']

def check_for_movement():
    """3축 동적 가속도 크기가 임계값을 넘는지 확인하여 움직임 감지"""
    if not is_initialized: _log("센서 미초기화"); return False
    _update_dynamic_accel()
    dynamic_accel_magnitude_sq = dynamic_accel['x']**2 + dynamic_accel['y']**2 + dynamic_accel['z']**2
    is_moving = dynamic_accel_magnitude_sq > (config.MOTION_THRESHOLD_MG ** 2)
    # if is_moving: # 디버깅용 상세 로그
    #    magnitude = math.sqrt(dynamic_accel_magnitude_sq)
    #    _log(f"움직임 감지: Mag={magnitude:.1f} mg (Thr={config.MOTION_THRESHOLD_MG})")
    return is_moving