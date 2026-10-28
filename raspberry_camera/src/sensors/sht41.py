"""Driver do SHT41, compatível com o barramento I²C usado pelo SHT20."""

import time


def calculate_crc(data):
    """Calcula o CRC-8 Sensirion, inicializado com 0xFF."""
    checksum = 0xFF
    for byte in data:
        checksum ^= byte
        for _ in range(8):
            if checksum & 0x80:
                checksum = ((checksum << 1) ^ 0x31) & 0xFF
            else:
                checksum = (checksum << 1) & 0xFF
    return checksum


class SHT41:
    """Obtém temperatura em Celsius e umidade relativa pelo barramento I²C."""

    def __init__(self, bus_number=1, address=0x44):
        """Abre o barramento I²C 1, usando o endereço padrão 0x44."""
        from smbus2 import SMBus

        self.bus = SMBus(bus_number)
        self.address = address

    def read(self):
        """Solicita uma medição de alta precisão e valida os CRCs recebidos."""
        from smbus2 import i2c_msg

        self.bus.write_byte(self.address, 0xFD)
        time.sleep(0.01)

        message = i2c_msg.read(self.address, 6)
        self.bus.i2c_rdwr(message)
        data = list(message)

        if calculate_crc(data[:2]) != data[2]:
            raise OSError('Falha de integridade CRC da temperatura no SHT41.')
        if calculate_crc(data[3:5]) != data[5]:
            raise OSError('Falha de integridade CRC da umidade no SHT41.')

        raw_temperature = (data[0] << 8) | data[1]
        raw_humidity = (data[3] << 8) | data[4]
        temperature = -45.0 + 175.0 * raw_temperature / 65535.0
        humidity = -6.0 + 125.0 * raw_humidity / 65535.0
        humidity = min(100.0, max(0.0, humidity))

        return {'temperature_c': temperature, 'humidity': humidity}

    def close(self):
        """Libera o barramento ao encerrar o programa."""
        self.bus.close()
