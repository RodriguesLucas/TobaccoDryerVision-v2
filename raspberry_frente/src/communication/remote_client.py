"""Consulta autenticada das leituras disponibilizadas pelo outro Raspberry."""

import json
import os
from urllib.request import Request, urlopen

from src.control.logic import is_valid_sample


def read_remote_sample(config):
    """Busca uma leitura e rejeita respostas inválidas ou antigas sem utilizar cache local."""
    if not config['remote_url']:
        raise ValueError('Configure o endereço do outro Raspberry em remote_url.')

    token = os.environ.get('CURING_TOKEN', '')
    request = Request(
        config['remote_url'],
        headers={'Authorization': 'Bearer ' + token},
    )

    with urlopen(request, timeout=config['network_timeout']) as response:
        sample = json.loads(response.read(4097))

    if not isinstance(sample, dict):
        raise ValueError('A resposta remota não contém um objeto de leitura.')

    sample_age = sample.get('age_seconds')
    if (
        sample.get('ok') is not True
        or not is_valid_sample(sample)
        or type(sample_age) not in (int, float)
        or not 0 <= sample_age <= config['max_sample_age']
    ):
        raise ValueError('A leitura do outro Raspberry está inválida ou antiga.')

    return sample
