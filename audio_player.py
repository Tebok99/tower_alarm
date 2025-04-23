# -*- coding: utf-8 -*-
import machine
import utime
import struct
import config # 설정값 가져오기

_log_func = None # 로깅 콜백 함수

def _log(message):
    """로깅 함수 호출 (설정된 경우)"""
    if _log_func:
        _log_func(f"[AudioPlayer] {message}")
    else:
        print(f"[AudioPlayer] {message}") # 콜백 없으면 콘솔 출력

def _find_wav_data_chunk(filepath):
    """WAV 파일에서 data 청크 정보 찾기 (내부 함수)"""
    sample_rate = bits_per_sample = num_channels = data_size = data_start = None
    try:
        with open(filepath, "rb") as f:
            riff_header = f.read(12)
            if riff_header[0:4] != b'RIFF' or riff_header[8:12] != b'WAVE':
                raise ValueError("Invalid WAV file: RIFF/WAVE header not found.")
            while True:
                chunk_header = f.read(8)
                if len(chunk_header) < 8: break
                chunk_id = chunk_header[0:4]
                chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
                if chunk_id == b'fmt ':
                    if chunk_size < 16: raise ValueError("Invalid WAV file: fmt chunk too small.")
                    fmt_data = f.read(chunk_size)
                    audio_format = struct.unpack('<H', fmt_data[0:2])[0]
                    if audio_format != 1: raise ValueError("Unsupported WAV format: Only PCM is supported.")
                    num_channels = struct.unpack('<H', fmt_data[2:4])[0]
                    sample_rate = struct.unpack('<I', fmt_data[4:8])[0]
                    bits_per_sample = struct.unpack('<H', fmt_data[14:16])[0]
                elif chunk_id == b'data':
                    data_size = chunk_size
                    data_start = f.tell()
                    break
                else:
                    f.seek(chunk_size, 1)
            if not all([sample_rate, bits_per_sample, num_channels, data_size is not None, data_start is not None]):
                raise ValueError("Invalid WAV file: Required chunks (fmt, data) not found or incomplete.")
            return sample_rate, bits_per_sample, num_channels, data_size, data_start
    except OSError as e:
        _log(f"WAV 파일 열기 오류: {e}")
        raise e
    except ValueError as e:
        _log(f"WAV 파일 분석 오류: {e}")
        raise e

def play_wav(log_callback=None):
    """설정된 WAV 파일을 I2S로 재생하고 릴레이 제어"""
    global _log_func
    _log_func = log_callback
    _log("WAV 재생 시도...")

    temp_i2s = None # 지역 I2S 객체

    try:
        # WAV 정보 얻기
        filepath = config.WAV_FILE_PATH
        sample_rate, bits_per_sample, num_channels, data_size, data_start = _find_wav_data_chunk(filepath)
        _log(f"WAV 정보: Rate={sample_rate}, Bits={bits_per_sample}, Chan={num_channels}, Size={data_size}")

        if bits_per_sample != 16: raise ValueError("16비트 오디오만 지원")
        if num_channels != 1: raise ValueError("모노 오디오만 지원")

        # I2S 초기화
        temp_i2s = machine.I2S(
            config.I2S_ID,
            sck=machine.Pin(config.PIN_I2S_SCK),
            ws=machine.Pin(config.PIN_I2S_WS),
            sd=machine.Pin(config.PIN_I2S_SD),
            mode=machine.I2S.TX, bits=16, format=machine.I2S.MONO,
            rate=sample_rate, ibuf=config.I2S_BUFFER_SIZE
        )

        # 데이터 스트리밍
        bytes_written = 0
        with open(filepath, "rb") as wav_file:
            wav_file.seek(data_start)
            remaining_data = data_size
            buffer = bytearray(config.I2S_BUFFER_SIZE)
            while remaining_data > 0:
                read_size = min(config.I2S_BUFFER_SIZE, remaining_data)
                num_read = wav_file.readinto(buffer, read_size)
                if num_read == 0: break
                try:
                    written = temp_i2s.write(memoryview(buffer)[:num_read])
                    bytes_written += written
                    if written != num_read:
                        _log(f"I2S 쓰기 불완전: {written}/{num_read}")
                        utime.sleep_ms(5)
                except Exception as e:
                    _log(f"I2S 쓰기 중 오류: {e}")
                    break # 쓰기 오류 시 중단
                remaining_data -= num_read
            _log(f"WAV 데이터 쓰기 완료: {bytes_written}/{data_size} bytes")
            utime.sleep_ms(200) # 버퍼 비우기 대기

    except Exception as e:
        _log(f"WAV 재생 과정 중 오류: {e}")

    finally:
        # 리소스 정리
        if temp_i2s:
            try:
                temp_i2s.deinit()
                _log("I2S 리소스 해제")
            except Exception as e: _log(f"I2S 해제 중 오류: {e}")
        _log("WAV 재생 종료/중단")