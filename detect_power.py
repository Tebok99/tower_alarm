class PowerManager:
    def __init__(self, pin):
        self.power_pin = Pin(pin, Pin.IN)
        self.led_pin = Pin(LED_PIN, Pin.OUT)

    def is_usb_powered(self):
        """USB 전원 연결 여부 확인"""
        # 아날로그 핀으로 전압 측정 (예시)
        return self.power_pin.value() == 1

    def handle_power_mode(self):
        """전원 모드에 따른 처리"""
        if self.is_usb_powered():
            # USB 연결 시: 정상 작동 모드
            self.led_pin.value(0)  # LED 끄기
        else:
            # 배터리 모드: 저전력 모드
            self.led_pin.value(1)  # LED 켜기