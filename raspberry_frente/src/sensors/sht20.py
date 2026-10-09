"""Driver do SHT20 baseado na leitura que funcionou no Raspberry do usuário."""

import time


def calculate_crc(data):
    """Calcula o CRC dos bytes recebidos para detectar erros de transmissão I²C."""
    checksum = 0
    for byte in data:
        checksum ^= byte
        for _ in range(8):
            if checksum & 0x80:
                checksum = ((checksum << 1) ^ 0x31) & 0xFF
            else:
                checksum = (checksum << 1) & 0xFF
    return checksum


class SHT20:
    """Obtém temperatura em Celsius e umidade relativa pelo barramento I²C."""

    def __init__(self, bus_number=1, address=0x40):
        """Abre o barramento utilizado pelos GPIOs 2 (SDA) e 3 (SCL)."""
        from smbus2 import SMBus

        self.bus = SMBus(bus_number)
        self.address = address

    def read_raw(self, command, conversion_delay):
        """Solicita uma medição, aguarda a conversão e valida os três bytes recebidos."""
        from smbus2 import i2c_msg

        self.bus.write_byte(self.address, command)
        time.sleep(conversion_delay)

        message = i2c_msg.read(self.address, 3)
        self.bus.i2c_rdwr(message)
        data = list(message)

        if calculate_crc(data[:2]) != data[2]:
            raise OSError('Falha de integridade CRC na leitura do SHT20.')

        # Os dois bits inferiores indicam estado e não pertencem à medição.
        return ((data[0] << 8) | data[1]) & 0xFFFC

    def read(self):
        """Converte os valores brutos e retorna um dicionário padronizado de leitura."""
        raw_humidity = self.read_raw(0xF5, 0.05)
        raw_temperature = self.read_raw(0xF3, 0.10)

        humidity = -6.0 + 125.0 * raw_humidity / 65536.0
        temperature = -46.85 + 175.72 * raw_temperature / 65536.0

        return {'temperature_c': temperature, 'humidity': humidity}

    def close(self):
        """Libera o barramento ao encerrar o programa."""
        self.bus.close()
