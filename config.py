# -*- coding: utf-8 -*-

# --- 하드웨어 핀 설정 ---
# LSM6DS3 (I2C0)
PIN_I2C0_SCL = 1
PIN_I2C0_SDA = 0
# BMP280 (I2C1) - Pico의 I2C1 기본 핀 또는 원하는 핀으로 설정
PIN_I2C1_SCL = 7 # GP7
PIN_I2C1_SDA = 6 # GP6
# 기타
PIN_LED = "LED"
# PIN_RELAY = 10 # --- 릴레이 핀 정의 제거 ---
PIN_ADC_VSYS = 3 # GP29

# --- I2C 설정 ---
I2C0_BUS_ID = 0
I2C1_BUS_ID = 1 # BMP280용 I2C 버스 ID. SoftI2C설정함.
I2C0_FREQ = 400000
I2C1_FREQ = 100000

# --- LSM6DS3 설정 ---
LSM6DS3_ADDR = 0x6A
REG_CTRL1_XL = 0x10
REG_CTRL2_G = 0x11    # 자이로 사용 시 필요
REG_STATUS = 0x1E
REG_OUTX_L_XL = 0x28
REG_OUTX_L_G = 0x22
# 센서 감도 및 ODR 설정 (ULP 모드 고려 - 12.5Hz 유지 또는 더 낮게 설정 가능)
ACCEL_SENSITIVITY = 0.061   # mg/LSB
# GYRO_SENSITIVITY = 4.375    # 자이로 사용 시 필요
ACCEL_ODR_CONFIG = b'\x10' # 12.5 Hz, ±2g (ULP 모드)
GYRO_ODR_CONFIG = b'\x00'  # 12.5 Hz, ±125 dps (b'\x12) (자이로 비활성화 시 b'\x00')
# 필터 및 오프셋
OFFSET_SAMPLE_COUNT = 50
# GYRO_LPF_ALPHA = 0.2    # 자이로 사용 시 필요
GRAVITY_FILTER_ALPHA = 0.1 # 중력 제거용 HPF(LPF 기반)
# 가속도 감지 임계값 (동적 가속도 기준, mg) - **민감한 반응, 작은 값 튜닝 필요**
MOTION_THRESHOLD_MG = 150

# --- BMP280 설정 ---
BMP280_ADDR = 0x76  # BMP280 기본 주소
PRESSURE_AVG_SAMPLES = 3   # 기압 측정 시 평균낼 샘플 수
ALTITUDE_CHANGE_THRESHOLD = 1.0 # 고도 변화 감지 임계값 (미터) - **민감한 반응, 작은 값 튜닝 필요**
PRESSURE_MONITOR_INTERVAL_MS = 1000 # 기압 모니터링 간격 (ms)
# 기압 모니터링 타임아웃 (ms) - 이 시간 동안 임계 고도값 변화 없으면 IDLE로 복귀
PRESSURE_MONITOR_TIMEOUT_MS = PRESSURE_MONITOR_INTERVAL_MS * 5
# 표준 해수면 기압 (Pa) - 고도 계산용 참조값
SEA_LEVEL_PRESSURE_PA = 101325.0

# --- I2S 및 WAV 설정 ---
I2S_ID = 0
PIN_I2S_SCK = 14
PIN_I2S_WS = 15
PIN_I2S_SD = 16
I2S_BUFFER_SIZE = 2048
WAV_FILE_PATH = "/wav/tower_crane_warning_fast.wav"

# --- 전압 관련 설정 ---
VOLTAGE_DIVIDER_RATIO = 3.0    # 전압 (V)
ADC_REF_VOLTAGE = 3.3    # 전압 (V)
LOW_BATT_THRESHOLD = 3.5    # 전압 (V)

# --- 로그 파일 ---
LOG_FILE_NAME = "log.txt" # 로그 파일 이름 변경

# --- 상태 정의 ---
STATE_INIT = 0
STATE_IDLE = 1              # 가속도계만 감지 (저전력 모드 가능)
STATE_MONITORING_PRESSURE = 2 # 가속 감지 후 기압 변화 모니터링 중
STATE_ACTION = 3            # 오디오 재생 중
STATE_LOW_BATT = 4
STATE_ERROR = 5

# --- 저전력 설정 ---
IDLE_SLEEP_MS = 200 # STATE_IDLE 상태에서 MCU sleep 시간 (ms)