# Raspberry: câmera, LED, SHT20 e relé

O relé 1 (GPIO 19) liga após a inicialização dos recursos e permanece ligado enquanto o programa roda. Ao encerrar com Ctrl+C, SIGTERM ou uma exceção que desenrole a execução, ele é desligado no bloco finally. O relé 2 (GPIO 26) não é inicializado. Não há consulta ao outro Raspberry.

O SHT20 usa I²C 1, endereço 0x40, GPIO 2 (SDA) e GPIO 3 (SCL). Mostra temperatura em °C/°F e umidade a cada 2 segundos. Uma falha de leitura é exibida no terminal; ela não altera o relé. A temperatura e a umidade não controlam o aquecimento nesta versão.

## Execução

```bash
sudo python3 run_camera.py
```

Para uma única foto, com o relé ligado durante a execução e desligado ao finalizar:

```bash
sudo python3 run_camera.py --once
```

Simulação sem hardware:

```bash
python3 run_camera.py --simulate --once
```

## Fotos e configuração

LED NeoPixel de 16 pixels no GPIO 18. Liga, aguarda 2 segundos, inicia a câmera CSI, aguarda mais 2 segundos, captura e apaga o LED. Foto BMP de 640 × 480 com exposição de 4000 µs e ColourGains (1.15, 1.0). Repete 30 minutos após cada captura. Destino: `/home/rodrigueslucas/Pictures/images/low/`.

Os ajustes ficam em `config/config.json`. `relay_active_low: true` significa LOW liga e HIGH desliga, conforme o código de teste informado. Se a placa de dois relés usar a polaridade inversa, ajuste para false antes de ligar a carga.

## Encerramento e limite

Ctrl+C solicita a parada. Se houver uma captura em andamento, ela termina ou atinge o timeout de 15 segundos antes do encerramento. Desligamento forçado (kill -9), falta de energia ou travamento do sistema não executam finally; o estado físico do relé depende do circuito. Como a fonte alimenta ventoinha e resistência juntas continuamente, use proteção térmica independente.

## Dependências

Picamera2 instalado pelo sistema; bibliotecas do LED, gpiozero e smbus2. O I²C precisa estar habilitado para abrir o SHT20. A lista Python está em requirements.txt.

## Histórico de temperatura e umidade (independente das fotos)

As medições do SHT20 são gravadas a cada `sample_interval` segundos (padrão: 2) em arquivos diários JSON Lines: `data/sensor_logs/leituras_YYYY-MM-DD.jsonl`. Cada linha tem `timestamp` com fuso horário de São Paulo, `sensor`, `temperature_c`, `temperature_f` e `humidity`. Isso permite cruzar as medições pelo horário com os registros do outro Raspberry, sem qualquer associação às fotos. O arquivo é aberto em modo de acréscimo e não apaga registros anteriores. A simulação grava separadamente em `data/sensor_logs/simulation/`.

Exemplo de linha:

```json
{"timestamp":"2026-10-21T13:50:00.000000-03:00","sensor":"SHT20","temperature_c":32.5,"temperature_f":90.5,"humidity":78.2}
```

O intervalo e a pasta podem ser ajustados no `config/config.json` (`sample_interval`, `sensor_log_directory` e `log_timezone`). O relógio de ambos os Raspberry Pi deve estar sincronizado para comparar as leituras.
