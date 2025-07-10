# app for only BMP388 Normal Mode
# 타워 알람 시스템 (BMP388 Normal Mode 전용)
import utime
from machine import Pin, I2C
import gc
from audio_player import AudioPlayer


class BMP388NormalMode:
    def __init__(self):
        # I2C 설정
        self.i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=100000)

        # BMP388 설정
        self.BMP388_ADDR = 0x77
        self.BMP388_ID = 0x50
        self.BMP388_STATUS = 0x03

        # LED 및 전원 핀
        self.led = Pin(25, Pin.OUT)

        # 보정 계수
        self.cal_data = {}
        self.t_fine = None

        # 고도 계산 관련
        self.sea_level_pressure = 101325.0  # 해수면 기압 (Pa)
        self.altitude_buffer = []
        self.buffer_size = 5  # 이동평균을 위한 버퍼 크기
        self.altitude_change_threshold = 2.0  # 2m 고도 변화 임계값
        self.reference_altitude = None
        self.reference_altitude_time = None
        self.interval_check_altitude = 5000 # 5 seconds 고도변화 측정 주기
        self.log_buffer = []
        self.interval_log_data = 60000  # 60 seconds


    def init_bmp388_normal_mode(self):
        """BMP388을 Normal Mode로 초기화"""
        try:
            # ID 확인
            chip_id = self.i2c.readfrom_mem(self.BMP388_ADDR, 0x00, 1)[0]
            if chip_id != self.BMP388_ID:
                print(f"잘못된 칩 ID: {chip_id}")
                return False

            # 소프트 리셋
            self.i2c.writeto_mem(self.BMP388_ADDR, 0x7E, bytes([0xB6]))
            utime.sleep_ms(10)

            # 보정 계수 읽기
            self.read_calibration_data()

            # osrs_t = 1 (×2), osrs_p = 4 (×16 standard)
            osr = 0x0C  # 00_001_100
            self.i2c.writeto_mem(self.BMP388_ADDR, 0x1C, bytes([osr]))

            # odr = 00101 (160ms standby)
            odr = 0x05  # 000_00101
            self.i2c.writeto_mem(self.BMP388_ADDR, 0x1D, bytes([odr]))

            # filter = 100 (IIR coeff 15)
            iir = 0x08  # 0000_100_0
            self.i2c.writeto_mem(self.BMP388_ADDR, 0x1F, bytes([iir]))

            # Normal Mode 설정 (3 << 4) | 3
            pwr_ctrl = 0x33  # 00_11_00_11
            self.i2c.writeto_mem(self.BMP388_ADDR, 0x1B, bytes([pwr_ctrl]))

            print("BMP388 Normal Mode 초기화 완료")
            return True

        except Exception as e:
            print(f"BMP388 초기화 실패: {e}")
            return False

    def read_calibration_data(self):
        """보정 계수 읽기"""
        cal_raw = self.i2c.readfrom_mem(self.BMP388_ADDR, 0x31, 21)

        t1 = (cal_raw[1] << 8) | cal_raw[0]
        t2 = (cal_raw[3] << 8) | cal_raw[2]
        t3 = cal_raw[4]
        if t3 & 0x80:
            t3 -= 0x100
        p1 = (cal_raw[6] << 8) | cal_raw[5]
        if p1 & 0x8000:
            p1 -= 0x10000
        p2 = (cal_raw[8] << 8) | cal_raw[7]
        if p2 & 0x8000:
            p2 -= 0x10000
        p3 = cal_raw[9]
        if p3 & 0x80:
            p3 -= 0x100
        p4 = cal_raw[10]
        if p4 & 0x80:
            p4 -= 0x100
        p5 = (cal_raw[12] << 8) | cal_raw[11]
        p6 = (cal_raw[14] << 8) | cal_raw[13]
        p7 = cal_raw[15]
        if p7 & 0x80:
            p7 -= 0x100
        p8 = cal_raw[16]
        if p8 & 0x80:
            p8 -= 0x100
        p9 = (cal_raw[18] << 8) | cal_raw[17]
        if p9 & 0x8000:
            p9 -= 0x10000
        p10 = cal_raw[19]
        if p10 & 0x80:
            p10 -= 0x100
        p11 = cal_raw[20]
        if p11 & 0x80:
            p11 -= 0x100

        # 보정 공식 적용
        self.cal_data['T1'] = t1 * 256.0
        self.cal_data['T2'] = t2 / 1073741824.0
        self.cal_data['T3'] = t3 / 281474976710656.0
        self.cal_data['P1'] = (p1 - 16384.0) / 1048576.0
        self.cal_data['P2'] = (p2 - 16384.0) / 536870912.0
        self.cal_data['P3'] = p3 / 4294967296.0
        self.cal_data['P4'] = p4 / 137438953472.0
        self.cal_data['P5'] = p5 * 8.0
        self.cal_data['P6'] = p6 / 64.0
        self.cal_data['P7'] = p7 / 256.0
        self.cal_data['P8'] = p8 / 32768.0
        self.cal_data['P9'] = p9 / 281474976710656.0
        self.cal_data['P10'] = p10 / 281474976710656.0
        self.cal_data['P11'] = p11 / 36893488147419103232.0


    def read_pressure_temperature(self):
        """Normal Mode에서 기압과 온도 읽기"""
        try:
            # 데이터 레지스터에서 읽기 (Normal Mode에서는 자동으로 업데이트됨)
            data = self.i2c.readfrom_mem(self.BMP388_ADDR, 0x04, 6)

            # 원시 기압 및 온도 추출
            raw_press = data[0] | (data[1] << 8) | (data[2] << 16)
            raw_temp = data[3] | (data[4] << 8) | (data[5] << 16)

            # 보정된 값 계산
            temp = self.compensate_temperature(raw_temp)
            pressure = self.compensate_pressure(raw_press)

            return pressure, temp

        except Exception as e:
            print(f"데이터 읽기 실패: {e}")
            return None, None

    def compensate_temperature(self, raw_temp):
        """온도 보정 계산"""
        partial_data1 = raw_temp - self.cal_data['T1']
        partial_data2 = partial_data1 * self.cal_data['T2']
        self.t_fine = partial_data2 + (partial_data1 * partial_data1) * self.cal_data['T3']
        return self.t_fine

    def compensate_pressure(self, raw_press):
        """기압 보정 계산"""
        if not hasattr(self, 't_fine'):
            return None

        partial_data1 = self.cal_data['P6'] * self.t_fine
        partial_data2 = self.cal_data['P7'] * (self.t_fine ** 2)
        partial_data3 = self.cal_data['P8'] * (self.t_fine ** 3)
        partial_out1 = self.cal_data['P5'] + partial_data1 + partial_data2 + partial_data3
        partial_data1 = self.cal_data['P2'] * self.t_fine
        partial_data2 = self.cal_data['P3'] * (self.t_fine ** 2)
        partial_data3 = self.cal_data['P4'] * (self.t_fine ** 3)
        partial_out2 = raw_press * (self.cal_data['P1'] + partial_data1 + partial_data2 + partial_data3)
        partial_data1 = raw_press ** 2
        partial_data2 = self.cal_data['P9'] + self.cal_data['P10'] * self.t_fine
        partial_data3 = partial_data1 * partial_data2
        partial_data4 = partial_data3 + (raw_press ** 3) * self.cal_data['P11']
        pressure = partial_out1 + partial_out2 + partial_data4
        return pressure


    def pressure_to_altitude(self, pressure):
        """기압을 고도로 변환 (국제표준대기 공식)"""
        if pressure <= 0:
            return None

        altitude = 44330.0 * (1.0 - (pressure / self.sea_level_pressure)**0.190263)
        return altitude

    def update_altitude_buffer(self, altitude):
        """고도 버퍼 업데이트 (이동평균용)"""
        self.altitude_buffer.append(altitude)
        if len(self.altitude_buffer) > self.buffer_size:
            self.altitude_buffer.pop(0)

    def get_smoothed_altitude(self):
        """이동평균으로 부드러운 고도값 계산"""
        if not self.altitude_buffer:
            return None
        return sum(self.altitude_buffer) / len(self.altitude_buffer)

    def check_altitude_change(self, current_altitude):
        """고도 변화 체크"""
        if self.reference_altitude is None:
            self.reference_altitude = current_altitude
            self.reference_altitude_time = utime.ticks_ms()
            print(f"현재 고도: {current_altitude:.2f}m, 기준 고도: {self.reference_altitude:.2f}m")

            return False

        altitude_change = abs(current_altitude - self.reference_altitude)
        print(f"고도 차이: {altitude_change:.2f}m, 현재 고도: {current_altitude:.2f}m, 기준 고도: {self.reference_altitude:.2f}m")

        current_time = utime.ticks_ms()
        if altitude_change >= self.altitude_change_threshold:
            print(f"고도 변화 감지: {altitude_change:.2f}m")
            # 기준 고도 업데이트
            self.reference_altitude = current_altitude
            self.reference_altitude_time = current_time
            return True

        # interval_check_altitude (ms) 경과 후 reference_altitude 설정
        if utime.ticks_diff(current_time, self.reference_altitude_time) >= self.interval_check_altitude:
            print(f"고도 변화 측정 주기 {self.interval_check_altitude/1000}초 경과")
            self.reference_altitude = current_altitude
            self.reference_altitude_time = current_time

        return False

    def blink_led_pattern(self, pattern_type):
        """LED 패턴 표시"""
        if pattern_type == "init_success":
            # 초기화 성공: 3번 짧게 깜빡
            for _ in range(3):
                self.led.on()
                utime.sleep_ms(100)
                self.led.off()
                utime.sleep_ms(100)
        elif pattern_type == "init_error":
            # 초기화 실패: 5번 빠르게 깜빡
            for _ in range(5):
                self.led.on()
                utime.sleep_ms(50)
                self.led.off()
                utime.sleep_ms(50)
        elif pattern_type == "measuring":
            # 측정 중: LED 켜기
            self.led.on()
        elif pattern_type == "altitude_change":
            # 고도 변화 감지: 길게 3번 깜빡
            for _ in range(3):
                self.led.on()
                utime.sleep_ms(300)
                self.led.off()
                utime.sleep_ms(200)
        elif pattern_type == "normal":
            # 정상 동작: LED 끄기
            self.led.off()

    def log_data(self):
        """데이터 로그 기록 (전력 절약을 위해 주기적으로만)"""
        try:
            if self.log_buffer is not None:
                # 파일에 기록 (전력 절약)
                with open("tower_log.csv", "a") as f:
                    f.write(self.log_buffer)

            self.log_buffer = []

        except Exception as e:
            print(f"로그 기록 실패: {e}")

    def calibrate_sea_level_pressure(self, samples=20):
        """해수면 기압 보정 (시작 시 현재 위치 기준)"""
        print("해수면 기압 보정 중...")
        pressure_samples = []

        for i in range(samples):
            pressure, temp = self.read_pressure_temperature()
            if pressure:
                pressure_samples.append(pressure)
                print(f"보정 샘플 {i + 1}/{samples}: {pressure:.2f} Pa")
            utime.sleep_ms(100)  # 100ms 간격

        if pressure_samples:
            self.sea_level_pressure = sum(pressure_samples) / len(pressure_samples)
            print(f"해수면 기압 설정: {self.sea_level_pressure:.2f} Pa")
            return True
        return False

    def run(self):
        """메인 실행 루프"""
        print("타워 알람 시스템 (기압계 전용) 시작")
        
        # BMP388 초기화
        if not self.init_bmp388_normal_mode():
            print("BMP388 초기화 실패")
            self.blink_led_pattern("init_error")
            return

        # # Audio Player 초기화 추가
        try:
            self.audio_player = AudioPlayer()
            if self.audio_player and self.audio_player.init():
                print("I2S Audio Player 초기화 성공")
            else:
                print("I2S Audio Player 초기화 실패")
                return
        except Exception as e:
            print(f"I2S Audio Player 초기화 중 예외: {e}")
            return

        # 초기화 완료 표시
        self.blink_led_pattern("init_success")

        # # 해수면 기압 보정
        # if not self.calibrate_sea_level_pressure():
        #     print("해수면 기압 보정 실패")
        #     self.blink_led_pattern("init_error")
        #     return

        print("시스템 준비 완료. 고도 변화 모니터링 시작...")

        # 로그 파일 헤더 작성
        try:
            with open("tower_log.csv", "w") as f:
                f.write("timestamp,pressure,temperature,altitude\n")
        except IOError:
            pass

        measurement_count = 0
        last_log_time = utime.ticks_ms()
        run_time = utime.ticks_ms()

        try:
            while True:
                self.blink_led_pattern("measuring")

                while (self.i2c.readfrom_mem(self.BMP388_ADDR, self.BMP388_STATUS, 1)[0] & 0x60) != 0x60:
                    utime.sleep_ms(5)
                # 기압 및 온도 측정
                pressure, temperature = self.read_pressure_temperature()
                print(f"측정 완료 소요시간: {utime.ticks_diff(utime.ticks_ms(),run_time):.2f} ms")

                if pressure and temperature:
                    # 고도 계산
                    altitude = self.pressure_to_altitude(pressure)

                    if altitude is not None:
                        # 고도 버퍼 업데이트
                        self.update_altitude_buffer(altitude)
                        smoothed_altitude = self.get_smoothed_altitude()

                        measurement_count += 1

                        # 상태 출력 (self.buffer_size 회 마다)
                        if measurement_count % self.buffer_size == 0:
                            print(f"기압: {pressure:.2f} Pa, 온도: {temperature:.2f}°C, 고도: {smoothed_altitude:.2f}m, 소요시간: {utime.ticks_diff(utime.ticks_ms(),run_time):.2f} ms")

                        # 고도 변화 확인 (버퍼가 충분히 찼을 때부터)
                        if len(self.altitude_buffer) >= self.buffer_size:
                            if self.check_altitude_change(smoothed_altitude):
                                print("경고: 2m 이상 고도 변화 감지!")
                                self.blink_led_pattern("altitude_change")

                                # 알람 소리 재생
                                # print("(가상)오디오 재생.")
                                self.audio_player.play_wav()  # wav 폴더의 wav file 재생

                                # 로그에 이벤트 기록
                                if self.log_buffer is not None:
                                    self.log_buffer.append(f"{utime.ticks_ms()},{pressure:.2f},{temperature:.2f},{smoothed_altitude:.2f}\n")
                                self.log_buffer = []

                        # 주기적 로그 기록 (1분마다)
                        current_time = utime.ticks_ms()
                        if utime.ticks_diff(current_time, last_log_time) > self.interval_log_data:
                            self.log_data()
                            last_log_time = current_time

                else:
                    print("센서 데이터 읽기 실패")
                    self.blink_led_pattern("init_error")

                self.blink_led_pattern("normal")
                run_time = utime.ticks_ms()

                # 대기 시간
                utime.sleep_ms(180)  # ORD+20ms 대기

                # 메모리 정리
                if measurement_count >= 50:
                    measurement_count = 0
                    gc.collect()

        except KeyboardInterrupt:
            print("프로그램 종료")

        except Exception as e:
            print(f"시스템 오류: {e}")
            self.blink_led_pattern("init_error")

        finally:
            # 정리 작업
            # 마지막 로그 데이터 저장
            if hasattr(self, 'log_buffer') and self.log_buffer:
                try:
                    with open("tower_log.csv", "a") as f:
                        f.write(self.log_buffer)
                except IOError:
                    print("tower_log.csv 파일 작성 오류")
            # LED 및 오디오 핀 정리
            if hasattr(self, 'led'):
                self.led.off()
            if hasattr(self, 'audio_player'):
                self.audio_player.deinit()

            print("타워 알람 시스템 종료")
    

# 메인 실행
if __name__ == "__main__":
    tower_alarm = BMP388NormalMode()
    tower_alarm.run()