def read_temperature(self):
    """온도 읽기"""
    data = self.read_bytes(BMP388_DATA_3, 3)
    temp_raw = (data[2] << 16) | (data[1] << 8) | data[0]

    # 보정 계산
    t1 = (temp_raw - self.par_t1)
    t2 = t1 * self.par_t2

    self.t_fine = t2 + (t1 * t1) * self.par_t3

    temp_comp = self.t_fine
    return temp_comp

def read_pressure(self):
    """압력 읽기"""
    # 온도 먼저 읽어서 t_fine 업데이트
    self.read_temperature()

    data = self.read_bytes(BMP388_DATA_0, 3)
    pres_raw = (data[2] << 16) | (data[1] << 8) | data[0]

    # 보정 계산
    p1 = self.par_p6 * self.t_fine
    p2 = self.par_p7 * (self.t_fine * self.t_fine)
    p3 = self.par_p8 * (self.t_fine * self.t_fine * self.t_fine)
    p4 = self.par_p5 + p1 + p2 + p3

    p1 = self.par_p2 * self.t_fine
    p2 = self.par_p3 * (self.t_fine * self.t_fine)
    p3 = self.par_p4 * (self.t_fine * self.t_fine * self.t_fine)
    p5 = p1 + p2 + p3

    p1 = pres_raw * self.par_p1
    p2 = p1 * p5
    p3 = p2 + (pres_raw * pres_raw) * self.par_p9
    p4 = p3 + (pres_raw * pres_raw * pres_raw) * self.par_p10
    p5 = p4 + (pres_raw * pres_raw * pres_raw * pres_raw) * self.par_p11

    pres_comp = p5 * self.par_p1

    return pres_comp

def read_altitude(self, sea_level_pressure=1013.25):
    """고도 계산"""
    pressure = self.read_pressure() / 100.0  # Pa -> hPa 변환
    altitude = 44330.0 * (1.0 - pow(pressure / sea_level_pressure, 0.1903))
    return altitude