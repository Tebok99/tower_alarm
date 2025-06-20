class StatusLED:
    def __init__(self, pin):
        self.led = Pin(pin, Pin.OUT)

    def on(self):
        """LED 켜기"""
        self.led.value(1)

    def off(self):
        """LED 끄기"""
        self.led.value(0)

    def toggle(self):
        """LED 상태 전환"""
        self.led.value(not self.led.value())

    def blink(self, count=3, interval=200):
        """LED 깜빡임 (비동기)"""
        # 타이머 사용하여 비동기 깜빡임 구현
        self._blink_count = count * 2  # 켜짐/꺼짐 각각 카운트
        self._blink_interval = interval
        self._blink_timer = Timer(-1)
        self._blink_timer.init(period=interval, mode=Timer.PERIODIC, callback=self._blink_callback)

    def _blink_callback(self, timer):
        """깜빡임 콜백 함수"""
        self.toggle()
        self._blink_count -= 1
        if self._blink_count <= 0:
            timer.deinit()