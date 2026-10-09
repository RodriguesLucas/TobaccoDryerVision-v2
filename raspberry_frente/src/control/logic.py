"""Regras de validação e controle; este módulo não acessa hardware."""

import math


def is_valid_sample(sample):
    """Verifica se temperatura e umidade são números finitos dentro da faixa do sensor."""
    if not isinstance(sample, dict):
        return False

    temperature = sample.get('temperature_c')
    humidity = sample.get('humidity')
    numeric_types = (int, float)

    return (
        type(temperature) in numeric_types
        and type(humidity) in numeric_types
        and math.isfinite(temperature)
        and math.isfinite(humidity)
        and -40 <= temperature <= 125
        and 0 <= humidity <= 100
    )


def to_fahrenheit(sample):
    """Converte a temperatura válida para °F; retorna None se a leitura for inválida."""
    if not is_valid_sample(sample):
        return None
    return sample['temperature_c'] * 1.8 + 32


def calculate_dew_point(sample):
    """Estima o ponto de orvalho do ar em °C; não mede a temperatura do acrílico."""
    if not is_valid_sample(sample) or sample['humidity'] == 0:
        return None

    temperature = sample['temperature_c']
    humidity = sample['humidity']
    coefficient = math.log(humidity / 100) + 17.62 * temperature / (243.12 + temperature)
    return 243.12 * coefficient / (17.62 - coefficient)


class HeatingController:
    """Calcula a demanda da fonte com histerese e bloqueio por sobretemperatura."""

    def __init__(self):
        """Inicia a demanda desligada e sem bloqueio térmico registrado."""
        self.is_on = False
        self.overheat_latched = False

    def update(self, local_sample, remote_sample, is_fresh, config):
        """Retorna (ligar_fonte, motivo) a partir das leituras e limites configurados.

        Ambas as leituras precisam estar válidas e recentes. A temperatura remota
        é registrada e validada, mas não define o alvo térmico da cápsula.
        """
        if not is_fresh or not is_valid_sample(local_sample) or not is_valid_sample(remote_sample):
            self.is_on = False
            return False, 'Dados ausentes, inválidos ou antigos.'

        maximum_temperature = config['max_capsule_c']
        if maximum_temperature is not None and local_sample['temperature_c'] >= maximum_temperature:
            self.is_on = False
            self.overheat_latched = True

        if self.overheat_latched:
            return False, 'Sobretemperatura: verifique o sistema antes de reiniciar.'

        if not config['heating_enabled']:
            self.is_on = False
            return False, 'Aquecimento desabilitado na configuração.'

        # Dois limiares evitam acionamentos repetidos próximos da mesma umidade.
        if local_sample['humidity'] >= config['humidity_on']:
            self.is_on = True
        elif local_sample['humidity'] <= config['humidity_off']:
            self.is_on = False

        reason = 'Demanda por umidade.' if self.is_on else 'Umidade abaixo do limiar de acionamento.'
        return self.is_on, reason
