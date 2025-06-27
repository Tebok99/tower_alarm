# -*- coding: utf-8 -*-
import ustruct
import utime
import machine
import config

# 모듈 전역 변수
_log_func = None
_i2s = None
is_initialized = False
wav_info = None
data_start_position = 44

def _log(message):
    global _log_func
    if _log_func:
        _log_func(f"[AudioPlayer] {message}")
    else:
        print(f"[AudioPlayer] {message}")


def init(log_callback=None):
    """I2S 오디오 초기화"""
    global _log_func, _i2s, is_initialized, wav_info, data_start_position
    _log_func = log_callback
    is_initialized = False

    try:
        with open(config.WAV_FILE_PATH, 'rb') as wav_file:
            # WAV 헤더 읽기 및 파싱
            header = wav_file.read(44)
            if len(header) != 44:
                _log("WAV 헤더 읽기 실패")
                return False

            wav_info = parse_wav_header(header)
            if wav_info is None:
                return False

            # 지원하는 포맷인지 확인
            if wav_info['format'] != 1:  # PCM만 지원
                _log(f"지원하지 않는 오디오 포맷: {wav_info['format']}")
                return False
            if wav_info['bits_per_sample'] != 16:
                _log("16비트 오디오만 지원")
                return False
            if wav_info['channels'] != 1:
                _log("모노 오디오만 지원")
                return False

            # 데이터 시작 위치 저장 (일반적으로 44바이트이지만 확실히 하기 위해)
            data_start_position = wav_file.tell()
            _log("WAV 파일 유효성 검사 완료.")

    except OSError as e:
        _log(f"WAV 파일 읽기 오류: {e}")
        return False

    try:
        _i2s = machine.I2S(
            config.I2S_ID,
            sck=machine.Pin(config.PIN_I2S_SCK),
            ws=machine.Pin(config.PIN_I2S_WS),
            sd=machine.Pin(config.PIN_I2S_SD),
            mode=machine.I2S.TX,
            bits=16,
            format=machine.I2S.MONO,
            rate=wav_info['sample_rate'],
            ibuf=config.I2S_BUFFER_SIZE
        )
        _log("I2S 오디오 초기화 완료")
        is_initialized = True
        return True
    except Exception as e:
        _log(f"I2S 초기화 중 오류: {e}")
        return False


def parse_wav_header(header):
    try:
        # RIFF 헤더
        riff_id = header[0:4]
        chunk_size = ustruct.unpack('<I', header[4:8])[0]
        format_id = header[8:12]

        # fmt 청크
        fmt_id = header[12:16]
        fmt_size = ustruct.unpack('<I', header[16:20])[0]
        audio_format = ustruct.unpack('<H', header[20:22])[0]
        num_channels = ustruct.unpack('<H', header[22:24])[0]
        sample_rate = ustruct.unpack('<I', header[24:28])[0]
        byte_rate = ustruct.unpack('<I', header[28:32])[0]
        block_align = ustruct.unpack('<H', header[32:34])[0]
        bits_per_sample = ustruct.unpack('<H', header[34:36])[0]

        # data 청크
        data_id = header[36:40]
        data_size = ustruct.unpack('<I', header[40:44])[0]

        _log(f"WAV 헤더 정보:")
        _log(f"  포맷: {audio_format} (1=PCM)")
        _log(f"  채널: {num_channels}")
        _log(f"  샘플링 레이트: {sample_rate} Hz")
        _log(f"  비트 레이트: {byte_rate} bps")
        _log(f"  비트 심도: {bits_per_sample} bit")
        _log(f"  데이터 크기: {data_size} bytes")

        return {
            'format': audio_format,
            'channels': num_channels,
            'sample_rate': sample_rate,
            'bits_per_sample': bits_per_sample,
            'data_size': data_size
        }

    except Exception as e:
        _log(f"WAV 헤더 파싱 오류: {e}")
        return None


def play_wav():
    """WAV 파일 재생"""
    global _i2s, is_initialized, wav_info, data_start_position
    if not is_initialized:
        _log("I2S가 초기화되지 않았습니다.")
        return False

    _log("오디오 재생 시작")

    try:
        with open(config.WAV_FILE_PATH, 'rb') as wav_file:
            wav_file.seek(data_start_position)
            # 청크 단위로 재생
            bytes_played = 0
            total_bytes = wav_info['data_size']

            while bytes_played < total_bytes:
                remaining = min(config.I2S_BUFFER_SIZE, total_bytes - bytes_played)
                buffer = wav_file.read(remaining)

                if len(buffer) == 0:
                    break

                _i2s.write(buffer)
                bytes_played += len(buffer)

        _log(f"오디오 재생 완료 ({bytes_played}/{total_bytes} bytes)")
        return True

    except Exception as e:
        _log(f"오디오 재생 중 오류: {e}")
        return False