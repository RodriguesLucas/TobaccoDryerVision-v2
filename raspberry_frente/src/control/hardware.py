"""Inicialização e desligamento dos relés e do anel LED."""


class CameraHardware:
    """Agrupa os recursos físicos e permite executar sem eles na simulação."""

    def __init__(self, config, simulation):
        """Cria saídas desligadas; fecha os recursos já criados se ocorrer uma falha."""
        self.sensor = None
        self.pixels = None
        self.power_relay = None
        self.reserved_relay = None

        if simulation:
            return

        try:
            from gpiozero import OutputDevice
            import board
            import neopixel
            from src.sensors.sht20 import SHT20

            active_high = not config['relay_active_low']
            self.power_relay = OutputDevice(19, active_high=active_high, initial_value=False)
            self.reserved_relay = OutputDevice(26, active_high=active_high, initial_value=False)
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

    def set_power(self, enabled):
        """Comanda a fonte da ventoinha e resistência; o relé reservado não é acionado."""
        if self.power_relay is not None:
            self.power_relay.value = enabled

    def set_light(self, enabled, color=(255, 255, 255)):
        """Atualiza todos os LEDs; envia preto para apagá-los quando enabled=False."""
        if self.pixels is not None:
            self.pixels.fill(tuple(color) if enabled else (0, 0, 0))
            self.pixels.show()

    def turn_off_relays(self):
        """Desliga as duas saídas antes de aguardar o encerramento dos trabalhadores."""
        for relay in (self.power_relay, self.reserved_relay):
            if relay is not None:
                relay.off()

    def close(self, close_sensor=True):
        """Libera cada recurso mesmo se outro falhar; evita fechar um sensor ainda em leitura."""
        self.turn_off_relays()
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
                for relay in (self.power_relay, self.reserved_relay):
                    if relay is not None:
                        relay.close()
