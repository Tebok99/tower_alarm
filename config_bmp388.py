from machine import I2C, Pin, Timer
import time
import uos

# BMP388 레지스터 주소 정의
BMP388_CHIP_ID = 0x00
BMP388_ERR_REG = 0x02
BMP388_STATUS = 0x03
BMP388_DATA_0 = 0x04
BMP388_DATA_1 = 0x05
BMP388_DATA_2 = 0x06
BMP388_DATA_3 = 0x07
BMP388_DATA_4 = 0x08
BMP388_DATA_5 = 0x09
BMP388_DATA_6 = 0x0A
BMP388_DATA_7 = 0x0B
BMP388_DATA_8 = 0x0C
BMP388_SENSORTIME_0 = 0x0D
BMP388_SENSORTIME_1 = 0x0E
BMP388_SENSORTIME_2 = 0x0F
BMP388_INT_STATUS = 0x11
BMP388_EVENT = 0x10
BMP388_INT_CTRL = 0x19
BMP388_FIFO_CONFIG_1 = 0x17
BMP388_FIFO_CONFIG_2 = 0x18
BMP388_FIFO_DATA = 0x14
BMP388_FIFO_LENGTH_0 = 0x12
BMP388_FIFO_LENGTH_1 = 0x13
BMP388_FIFO_WTM_0 = 0x15
BMP388_FIFO_WTM_1 = 0x16
BMP388_PWR_CTRL = 0x1B
BMP388_OSR = 0x1C
BMP388_ODR = 0x1D
BMP388_CONFIG = 0x1F
BMP388_CALIB_DATA = 0x31
BMP388_CMD = 0x7E

# 핀 정의
I2C_SCL_PIN = 22  # I2C 클럭 핀 (ESP32 기준)
I2C_SDA_PIN = 21  # I2C 데이터 핀 (ESP32 기준)
LED_PIN = 2       # 상태 LED 핀

# 센서 설정 상수
SEALEVELPRESSURE_HPA = 1013.25
ALTITUDE_THRESHOLD = 1.0       # 1미터 임계값
MEASUREMENT_INTERVAL = 1000    # 측정 주기 (ms)
SOUND_DURATION = 13000         # 소리 재생 시간 (13초)

# 전역 변수
base_altitude = 0.0
current_altitude = 0.0
altitude_difference = 0.0
last_measurement_time = 0
sound_start_time = 0
is_playing_sound = False
sensor_initialized = False

# BMP388 클래스 정의
class BMP388:
    def __init__(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        self.calib_data = {}
        self.t_fine = 0

        # 보정 데이터 상수
        self.par_t1 = 0
        self.par_t2 = 0
        self.par_t3 = 0
        self.par_p1 = 0
        self.par_p2 = 0
        self.par_p3 = 0
        self.par_p4 = 0
        self.par_p5 = 0
        self.par_p6 = 0
        self.par_p7 = 0
        self.par_p8 = 0
        self.par_p9 = 0
        self.par_p10 = 0
        self.par_p11 = 0

        # 센서 초기화
        self.chip_id = self.read_byte(BMP388_CHIP_ID)
        if self.chip_id != 0x50:
            raise Exception("BMP388 센서를 찾을 수 없습니다!")

        self.get_calib_data()
        self.set_config()