class Logger:
    def __init__(self, filename="log.txt"):
        self.filename = filename
        # 로그 파일 초기화
        try:
            with open(self.filename, "w") as f:
                f.write("Time,Temperature,Pressure,Altitude,Difference\n")
        except:
            print("로그 파일 생성 실패")

    def log_data(self, temperature, pressure, altitude, difference):
        """데이터 로깅"""
        try:
            with open(self.filename, "a") as f:
                f.write(f"{time.ticks_ms()},{temperature:.2f},{pressure:.2f},{altitude:.2f},{difference:.2f}\n")
        except:
            print("로그 기록 실패")