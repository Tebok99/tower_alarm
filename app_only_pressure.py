import machine
import time
import math
from machine import Pin, I2C, PWM
import os
import gc


class BMP280NormalMode:
    def __init__(self):
        # I2C 설정
        self.i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

        # BMP280 설정
        self.BMP280_ADDR = 0x76
        self.BMP280_ID = 0x58

        # LED 및 전원 핀
        self.led = Pin(25, Pin.OUT)
        self.usb_detect = Pin(24, Pin.IN, Pin.PULL_UP)

        # 보정 계수
        self.cal_data = {}

        # 고도 계산 관련
        self.sea_level_pressure = 101325.0  # 해수면 기압 (Pa)
        self.altitude_buffer = []
        self.buffer_size = 10  # 이동평균을 위한 버퍼 크기
        self.altitude_change_threshold = 2.0  # 2m 고도 변화 임계값
        self.reference_altitude = None

        # 오디오 관련
        self.audio_pin = PWM(Pin(28))  # 스피커 핀

    def init_bmp280_normal_mode(self):
        """BMP280을 Normal Mode로 초기화"""
        try:
            # ID 확인
            chip_id = self.i2c.readfrom_mem(self.BMP280_ADDR, 0xD0, 1)[0]
            if chip_id != self.BMP280_ID:
                print(f"잘못된 칩 ID: {chip_id}")
                return False

            # 소프트 리셋
            self.i2c.writeto_mem(self.BMP280_ADDR, 0xE0, bytes([0xB6]))
            time.sleep(0.01)

            # 보정 계수 읽기
            self.read_calibration_data()

            # Normal Mode 설정
            # osrs_t = 1 (×1), osrs_p = 4 (×4 standard), mode = 11 (normal)
            ctrl_meas = 0x27  # 001_001_11
            self.i2c.writeto_mem(self.BMP280_ADDR, 0xF4, bytes([ctrl_meas]))

            # Config 레지스터 설정
            # t_sb = 100 (500ms standby), filter = 100 (IIR coeff 4), spi3w_en = 0
            config = 0x90  # 100_100_0_0
            self.i2c.writeto_mem(self.BMP280_ADDR, 0xF5, bytes([config]))

            print("BMP280 Normal Mode 초기화 완료")
            return True

        except Exception as e:
            print(f"BMP280 초기화 실패: {e}")
            return False

    def read_calibration_data(self):
        """보정 계수 읽기"""
        cal_raw = self.i2c.readfrom_mem(self.BMP280_ADDR, 0x88, 24)

        self.cal_data['T1'] = int.from_bytes(cal_raw[0:2], 'little')
        self.cal_data['T2'] = int.from_bytes(cal_raw[2:4], 'little', True)
        self.cal_data['T3'] = int.from_bytes(cal_raw[4:6], 'little', True)
        self.cal_data['P1'] = int.from_bytes(cal_raw[6:8], 'little')
        self.cal_data['P2'] = int.from_bytes(cal_raw[8:10], 'little', True)
        self.cal_data['P3'] = int.from_bytes(cal_raw[10:12], 'little', True)
        self.cal_data['P4'] = int.from_bytes(cal_raw[12:14], 'little', True)
        self.cal_data['P5'] = int.from_bytes(cal_raw[14:16], 'little', True)
        self.cal_data['P6'] = int.from_bytes(cal_raw[16:18], 'little', True)
        self.cal_data['P7'] = int.from_bytes(cal_raw[18:20], 'little', True)
        self.cal_data['P8'] = int.from_bytes(cal_raw[20:22], 'little', True)
        self.cal_data['P9'] = int.from_bytes(cal_raw[22:24], 'little', True)

    def read_pressure_temperature(self):
        """Normal Mode에서 기압과 온도 읽기"""
        try:
            # 데이터 레지스터에서 읽기 (Normal Mode에서는 자동으로 업데이트됨)
            data = self.i2c.readfrom_mem(self.BMP280_ADDR, 0xF7, 6)

            # 20비트 압력 데이터
            press_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            # 20비트 온도 데이터
            temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

            # 보정된 값 계산
            temp = self.compensate_temperature(temp_raw)
            pressure = self.compensate_pressure(press_raw)

            return pressure, temp

        except Exception as e:
            print(f"데이터 읽기 실패: {e}")
            return None, None

    def compensate_temperature(self, raw_temp):
        """온도 보정 계산"""
        var1 = (raw_temp / 16384.0 - self.cal_data['T1'] / 1024.0) * self.cal_data['T2']
        var2 = ((raw_temp / 131072.0 - self.cal_data['T1'] / 8192.0) ** 2) * self.cal_data['T3']
        self.t_fine = var1 + var2
        return self.t_fine / 5120.0

    def compensate_pressure(self, raw_press):
        """기압 보정 계산"""
        if not hasattr(self, 't_fine'):
            return None

        var1 = self.t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * self.cal_data['P6'] / 32768.0
        var2 = var2 + var1 * self.cal_data['P5'] * 2.0
        var2 = var2 / 4.0 + self.cal_data['P4'] * 65536.0
        var1 = (self.cal_data['P3'] * var1 * var1 / 524288.0 + self.cal_data['P2'] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.cal_data['P1']

        if var1 == 0:
            return None

        pressure = 1048576.0 - raw_press
        pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
        var1 = self.cal_data['P9'] * pressure * pressure / 2147483648.0
        var2 = pressure * self.cal_data['P8'] / 32768.0
        pressure = pressure + (var1 + var2 + self.cal_data['P7']) / 16.0

        return pressure

    def pressure_to_altitude(self, pressure):
        """기압을 고도로 변환 (국제표준대기 공식)"""
        if pressure <= 0:
            return None

        altitude = 44330.0 * (1.0 - pow(pressure / self.sea_level_pressure, 0.1903))
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
            return False

        altitude_change = abs(current_altitude - self.reference_altitude)

        if altitude_change >= self.altitude_change_threshold:
            print(f"고도 변화 감지: {altitude_change:.2f}m")
            # 기준 고도 업데이트
            self.reference_altitude = current_altitude
            return True

        return False

    def play_alarm_sound(self):
        """알람 소리 재생"""
        try:
            # 간단한 비프음 (1000Hz, 500ms)
            self.audio_pin.freq(1000)
            self.audio_pin.duty_u16(32768)  # 50% duty cycle
            time.sleep(0.5)
            self.audio_pin.duty_u16(0)  # 소리 끄기

            time.sleep(0.1)

            # 두 번째 비프음 (1500Hz, 500ms)
            self.audio_pin.freq(1500)
            self.audio_pin.duty_u16(32768)
            time.sleep(0.5)
            self.audio_pin.duty_u16(0)

        except Exception as e:
            print(f"알람 소리 재생 실패: {e}")

    def play_wav_file(self, filename):
        """WAV 파일 재생 (간단한 구현)"""
        try:
            wav_path = f"wav/{filename}"
            if "wav" in os.listdir() and filename in os.listdir("wav"):
                print(f"WAV 파일 재생: {filename}")
                # 실제 WAV 파일 재생을 위해서는 별도의 라이브러리 필요
                # 여기서는 대체용 비프음 재생
                self.play_alarm_sound()
            else:
                print(f"WAV 파일을 찾을 수 없음: {filename}")
                self.play_alarm_sound()  # 대체 알람음
        except Exception as e:
            print(f"WAV 파일 재생 실패: {e}")
            self.play_alarm_sound()

    def blink_led_pattern(self, pattern_type):
        """LED 패턴 표시"""
        if pattern_type == "init_success":
            # 초기화 성공: 3번 짧게 깜빡
            for _ in range(3):
                self.led.on()
                time.sleep(0.1)
                self.led.off()
                time.sleep(0.1)
        elif pattern_type == "init_error":
            # 초기화 실패: 5번 빠르게 깜빡
            for _ in range(5):
                self.led.on()
                time.sleep(0.05)
                self.led.off()
                time.sleep(0.05)
        elif pattern_type == "measuring":
            # 측정 중: LED 켜기
            self.led.on()
        elif pattern_type == "altitude_change":
            # 고도 변화 감지: 길게 3번 깜빡
            for _ in range(3):
                self.led.on()
                time.sleep(0.3)
                self.led.off()
                time.sleep(0.2)
        elif pattern_type == "normal":
            # 정상 동작: LED 끄기
            self.led.off()

    def is_battery_powered(self):
        """배터리 전원 여부 확인"""
        return self.usb_detect.value() == 1

    def log_data(self, pressure, temperature, altitude):
        """데이터 로그 기록 (전력 절약을 위해 주기적으로만)"""
        try:
            timestamp = time.ticks_ms()
            log_entry = f"{timestamp},{pressure:.2f},{temperature:.2f},{altitude:.2f}\n"

            # 메모리에 임시 저장 후 주기적으로 파일에 기록
            if not hasattr(self, 'log_buffer'):
                self.log_buffer = []

            self.log_buffer.append(log_entry)

            # 10개 데이터마다 파일에 기록 (전력 절약)
            if len(self.log_buffer) >= 10:
                with open("tower_log.csv", "a") as f:
                    f.writelines(self.log_buffer)
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
            time.sleep(0.5)  # 500ms 간격

        if pressure_samples:
            self.sea_level_pressure = sum(pressure_samples) / len(pressure_samples)
            print(f"해수면 기압 설정: {self.sea_level_pressure:.2f} Pa")
            return True
        return False

    def run(self):
        """메인 실행 루프"""
        print("타워 알람 시스템 (기압계 전용) 시작")

        # USB 연결 확인
        if not self.is_battery_powered():
            print("USB 연결됨. 자동 실행하지 않음.")
            return

        # BMP280 초기화
        if not self.init_bmp280_normal_mode():
            print("BMP280 초기화 실패")
            self.blink_led_pattern("init_error")
            return

        # 초기화 완료 표시
        self.blink_led_pattern("init_success")

        # 해수면 기압 보정
        if not self.calibrate_sea_level_pressure():
            print("해수면 기압 보정 실패")
            self.blink_led_pattern("init_error")
            return

        print("시스템 준비 완료. 고도 변화 모니터링 시작...")

        # 로그 파일 헤더 작성
        try:
            with open("tower_log.csv", "w") as f:
                f.write("timestamp,pressure,temperature,altitude\n")
        except:
            pass

        measurement_count = 0
        last_log_time = time.ticks_ms()

        try:
            while True:
                self.blink_led_pattern("measuring")

                # 기압 및 온도 측정
                pressure, temperature = self.read_pressure_temperature()

                if pressure and temperature:
                    # 고도 계산
                    altitude = self.pressure_to_altitude(pressure)

                    if altitude is not None:
                        # 고도 버퍼 업데이트
                        self.update_altitude_buffer(altitude)
                        smoothed_altitude = self.get_smoothed_altitude()

                        measurement_count += 1

                        # 상태 출력 (10회마다)
                        if measurement_count % 10 == 0:
                            print(f"기압: {pressure:.2f} Pa, 온도: {temperature:.2f}°C, 고도: {smoothed_altitude:.2f}m")

                        # 고도 변화 확인 (버퍼가 충분히 찼을 때부터)
                        if len(self.altitude_buffer) >= self.buffer_size:
                            if self.check_altitude_change(smoothed_altitude):
                                print("경고: 2m 이상 고도 변화 감지!")
                                self.blink_led_pattern("altitude_change")

                                # 알람 소리 재생
                                self.play_wav_file("alarm.wav")  # wav 폴더의 alarm.wav 재생

                                # 로그에 이벤트 기록
                                current_time = time.ticks_ms()
                                if not hasattr(self, 'log_buffer'):
                                    self.log_buffer = []
                                self.log_buffer.append(
                                    f"{current_time},EVENT,ALTITUDE_CHANGE,{smoothed_altitude:.2f}\n")

                        # 주기적 로그 기록 (1분마다)
                        current_time = time.ticks_ms()
                        if time.ticks_diff(current_time, last_log_time) > 60000:  # 60초
                            self.log_data(pressure, temperature, smoothed_altitude)
                            last_log_time = current_time

                else:
                    print("센서 데이터 읽기 실패")
                    self.blink_led_pattern("init_error")

                self.blink_led_pattern("normal")

                # Normal Mode에서는 센서가 자동으로 500ms마다 측정하므로
                # 충분한 대기 시간 확보
                time.sleep(0.6)  # 600ms 대기

                # 메모리 정리
                if measurement_count % 50 == 0:
                    gc.collect()

        except KeyboardInterrupt:
            print("프로그램 종료")
            # 마지막 로그 데이터 저장
            if hasattr(self, 'log_buffer') and self.log_buffer:
                try:
                    with open("tower_log.csv", "a") as f:
                        f.writelines(self.log_buffer)
                except:
                    pass

        except Exception as e:
            print(f"시스템 오류: {e}")
            self.blink_led_pattern("init_error")

        finally:
            # 정리 작업
            self.led.off()
            if hasattr(self, 'audio_pin'):
                self.audio_pin.duty_u16(0)


# 메인 실행
if __name__ == "__main__":
    tower_alarm = BMP280NormalMode()
    tower_alarm.run()