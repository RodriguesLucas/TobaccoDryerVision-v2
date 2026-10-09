"""Inicializa o LED, o SHT20 e o relé 1 deste Raspberry."""


class CameraHardware:
    """Inicializa a iluminação utilizada na captura das fotografias."""

    def __init__(self, config, simulation):
        """Cria o anel LED apagado; a simulação não acessa o hardware."""
        self.pixels = None
        self.sensor = None
        self.power_relay = None
        if simulation:
            return
        try:
            import board
            import neopixel
            from gpiozero import OutputDevice
            from src.sensors.sht20 import SHT20

            # O relé começa desligado. Apenas o GPIO 19 é utilizado.
            self.power_relay = OutputDevice(19, active_high=not config['relay_active_low'], initial_value=False)
            self.sensor = SHT20()

            self.pixels = neopixel.NeoPixel(
                board.D18,
                config['led_count'],
                brightness=config['led_brightness'],
                auto_write=False,
                pixel_order=neopixel.GRB,
            )
            self.set_light(False)
        except BaseException:
            self.close()
            raise

    def set_light(self, enabled, color=(255, 255, 255)):
        """Envia a cor para todos os LEDs ou envia preto para apagá-los."""
        if self.pixels is not None:
            self.pixels.fill(tuple(color) if enabled else (0, 0, 0))
            self.pixels.show()

    def set_power(self, enabled):
        """Liga ou desliga o relé 1 que alimenta a fonte da ventoinha e resistência."""
        if self.power_relay is not None:
            self.power_relay.value = enabled

    def close(self, close_sensor=True):
        """Desliga o relé primeiro e libera os recursos mesmo se outro falhar."""
        try:
            self.set_power(False)
        finally:
            try:
                if self.pixels is not None:
                    try:
                        self.set_light(False)
                    finally:
                        self.pixels.deinit()
            finally:
                try:
                    if self.sensor is not None and close_sensor:
                        self.sensor.close()
                finally:
                    if self.power_relay is not None:
                        self.power_relay.close()
