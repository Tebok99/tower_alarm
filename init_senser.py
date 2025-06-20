def get_calib_data(self):
    """보정 데이터 읽기"""
    calib = self.read_bytes(BMP388_CALIB_DATA, 21)

    # 온도 보정 데이터
    self.par_t1 = ((calib[1] << 8) | calib[0]) / 2**8.0
    self.par_t2 = ((calib[3] << 8) | calib[2]) / 2**30.0
    self.par_t3 = calib[4] / 2**48.0

    # 압력 보정 데이터
    self.par_p1 = (calib[6] << 8) | calib[5]
    self.par_p2 = ((calib[8] << 8) | calib[7]) / 2**10.0
    self.par_p3 = calib[9] / 2**8.0
    self.par_p4 = calib[10] / 2**4.0
    self.par_p5 = (calib[12] << 8) | calib[11]
    self.par_p6 = ((calib[14] << 8) | calib[13]) / 2**14.0
    self.par_p7 = calib[15] / 2**8.0
    self.par_p8 = calib[16] / 2**16.0
    self.par_p9 = ((calib[18] << 8) | calib[17]) / 2**20.0
    self.par_p10 = calib[19] / 2**16.0
    self.par_p11 = calib[20] / 2**32.0

def set_config(self):
    """센서 설정"""
    # 소프트 리셋
    self.write_byte(BMP388_CMD, 0xB6)
    time.sleep(0.2)

    # 전원 모드 설정 (압력 및 온도 측정 활성화)
    self.write_byte(BMP388_PWR_CTRL, 0x33)

    # 오버샘플링 설정
    # 온도 x8, 압력 x4 오버샘플링
    self.write_byte(BMP388_OSR, 0x03)

    # ODR(Output Data Rate) 설정 - 50Hz
    self.write_byte(BMP388_ODR, 0x03)

    # IIR 필터 설정 - 계수 3
    self.write_byte(BMP388_CONFIG, 0x02)

    # 잠시 대기
    time.sleep(0.1)

def read_byte(self, reg):
    """단일 바이트 읽기"""
    return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

def read_bytes(self, reg, length):
    """여러 바이트 읽기"""
    return self.i2c.readfrom_mem(self.addr, reg, length)

def write_byte(self, reg, value):
    """단일 바이트 쓰기"""
    self.i2c.writeto_mem(self.addr, reg, bytes([value]))