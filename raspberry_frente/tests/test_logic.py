"""Verifica regras de controle sem depender de Raspberry ou sensores reais."""

import unittest
from src.control.logic import HeatingController, is_valid_sample, calculate_dew_point


class HeatingControllerTests(unittest.TestCase):
    """Protege as regras de histerese, falhas de leitura e limite térmico."""

    def setUp(self):
        """Prepara dados artificiais para cada teste, sem reutilizar estado anterior."""
        self.controller = HeatingController()
        self.config = {
            'max_capsule_c': 40,
            'heating_enabled': True,
            'humidity_on': 85,
            'humidity_off': 75,
        }
        self.remote_sample = {'temperature_c': 50, 'humidity': 80}

    def update_controller(self, humidity=90, temperature=30, is_fresh=True):
        """Simplifica os testes retornando somente a demanda calculada para a fonte."""
        local_sample = {'temperature_c': temperature, 'humidity': humidity}
        enabled, _ = self.controller.update(local_sample, self.remote_sample, is_fresh, self.config)
        return enabled

    def test_hysteresis(self):
        """Mantém a demanda entre os limiares e desliga ao atingir o limiar inferior."""
        self.assertTrue(self.update_controller())
        self.assertTrue(self.update_controller(humidity=80))
        self.assertFalse(self.update_controller(humidity=70))

    def test_stale_sample_turns_power_off(self):
        """Uma leitura antiga não pode manter a fonte acionada."""
        self.update_controller()
        self.assertFalse(self.update_controller(is_fresh=False))

    def test_remote_failure_turns_power_off(self):
        """A perda do sensor remoto bloqueia o acionamento."""
        self.update_controller()
        enabled, _ = self.controller.update({'temperature_c': 30, 'humidity': 90}, None, False, self.config)
        self.assertFalse(enabled)

    def test_overheat_latches_shutdown(self):
        """O retorno da temperatura à faixa normal não rearma automaticamente a fonte."""
        self.update_controller()
        self.assertFalse(self.update_controller(temperature=40))
        self.assertFalse(self.update_controller(temperature=30))

    def test_disabled_configuration(self):
        """A configuração desabilitada prevalece sobre a demanda por umidade."""
        self.config['heating_enabled'] = False
        self.assertFalse(self.update_controller())

    def test_invalid_numeric_value(self):
        """Rejeita valores não finitos recebidos do sensor."""
        self.assertFalse(is_valid_sample({'temperature_c': float('nan'), 'humidity': 80}))

    def test_dew_point_at_saturation(self):
        """A 100% de UR, o ponto de orvalho coincide com a temperatura do ar."""
        sample = {'temperature_c': 30, 'humidity': 100}
        self.assertAlmostEqual(calculate_dew_point(sample), 30)


if __name__ == '__main__':
    unittest.main()
