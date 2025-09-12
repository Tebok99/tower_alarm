# -*- coding: utf-8 -*-
import ustruct
import machine
import config

class AudioPlayer:
    def __init__(self, log_callback=None):
        self._log_func = log_callback
        self._i2s = None
        self.is_initialized = False
        self.wav_info = None
        self.data_start_position = 44
        # 핀 객체를 멤버로 관리
        self.pin_sck = machine.Pin(config.PIN_I2S_SCK, machine.Pin.OUT)
        self.pin_ws  = machine.Pin(config.PIN_I2S_WS,  machine.Pin.OUT)
        self.pin_sd  = machine.Pin(config.PIN_I2S_SD,  machine.Pin.OUT)

    def _log(self, message):
        if self._log_func:
            self._log_func(f"[AudioPlayer] {message}")
        else:
            print(f"[AudioPlayer] {message}")

    def init(self):
        self.is_initialized = False

        try:
            with open(config.WAV_FILE_PATH, 'rb') as wav_file:
                header = wav_file.read(44)
                if len(header) != 44:
                    self._log("WAV 헤더 읽기 실패")
                    return False

                self.wav_info = self.parse_wav_header(header)
                if self.wav_info is None:
                    return False

                if self.wav_info['format'] != 1:
                    self._log(f"지원하지 않는 오디오 포맷: {self.wav_info['format']}")
                    return False
                if self.wav_info['bits_per_sample'] != 16:
                    self._log("16비트 오디오만 지원")
                    return False
                if self.wav_info['channels'] != 1:
                    self._log("모노 오디오만 지원")
                    return False

                self.data_start_position = wav_file.tell()
                self._log("WAV 파일 유효성 검사 완료.")

        except OSError as e:
            self._log(f"WAV 파일 읽기 오류: {e}")
            return False

        try:
            self._i2s = machine.I2S(
                config.I2S_ID,
                sck=self.pin_sck,
                ws=self.pin_ws,
                sd=self.pin_sd,
                mode=machine.I2S.TX,
                bits=16,
                format=machine.I2S.MONO,
                rate=self.wav_info['sample_rate'],
                ibuf=config.I2S_BUFFER_SIZE
            )
            self._log("I2S 오디오 초기화 완료")
            self.is_initialized = True
            return True
        except Exception as e:
            self._log(f"I2S 초기화 중 오류: {e}")
            return False

    def parse_wav_header(self, header):
        try:
            riff_id = header[0:4]
            chunk_size = ustruct.unpack('<I', header[4:8])[0]
            format_id = header[8:12]
            fmt_id = header[12:16]
            fmt_size = ustruct.unpack('<I', header[16:20])[0]
            audio_format = ustruct.unpack('<H', header[20:22])[0]
            num_channels = ustruct.unpack('<H', header[22:24])[0]
            sample_rate = ustruct.unpack('<I', header[24:28])[0]
            byte_rate = ustruct.unpack('<I', header[28:32])[0]
            block_align = ustruct.unpack('<H', header[32:34])[0]
            bits_per_sample = ustruct.unpack('<H', header[34:36])[0]
            data_id = header[36:40]
            data_size = ustruct.unpack('<I', header[40:44])[0]

            self._log(f"WAV 헤더 정보:")
            self._log(f"  포맷: {audio_format} (1=PCM)")
            self._log(f"  채널: {num_channels}")
            self._log(f"  샘플링 레이트: {sample_rate} Hz")
            self._log(f"  비트 레이트: {byte_rate} bps")
            self._log(f"  비트 심도: {bits_per_sample} bit")
            self._log(f"  데이터 크기: {data_size} bytes")

            return {
                'format': audio_format,
                'channels': num_channels,
                'sample_rate': sample_rate,
                'bits_per_sample': bits_per_sample,
                'data_size': data_size
            }
        except Exception as e:
            self._log(f"WAV 헤더 파싱 오류: {e}")
            return None

    def play_wav(self):
        if not self.is_initialized:
            self._log("I2S가 초기화되지 않았습니다.")
            return False

        self._log("오디오 재생 시작")

        try:
            with open(config.WAV_FILE_PATH, 'rb') as wav_file:
                wav_file.seek(self.data_start_position)
                bytes_played = 0
                total_bytes = self.wav_info['data_size']

                while bytes_played < total_bytes:
                    remaining = min(config.I2S_BUFFER_SIZE, total_bytes - bytes_played)
                    buffer = wav_file.read(remaining)

                    if len(buffer) == 0:
                        break

                    self._i2s.write(buffer)
                    bytes_played += len(buffer)

            self._log(f"오디오 재생 완료 ({bytes_played}/{total_bytes} bytes)")
            return True

        except Exception as e:
            self._log(f"오디오 재생 중 오류: {e}")
            return False

    def deinit(self):
        """I2S 및 핀 리소스 해제"""
        if self._i2s:
            try:
                self._i2s.deinit()
                self._log("I2S 리소스 해제 완료")
            except Exception as e:
                self._log(f"I2S 해제 중 오류: {e}")
            self._i2s = None
        # 핀을 안전하게 입력모드로 변경
        for pin in [self.pin_sck, self.pin_ws, self.pin_sd]:
            try:
                pin.init(mode=machine.Pin.IN)
            except Exception as e:
                self._log(f"핀 해제 중 오류: {e}")
        self.is_initialized = False