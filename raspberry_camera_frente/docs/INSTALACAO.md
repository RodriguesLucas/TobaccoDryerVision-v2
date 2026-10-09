# Raspberry da câmera e cápsula

Código experimental para o hardware informado. Não executa classificação dos modelos,
Laya, máquina de estados da cura ou flap: essas funções pertencem ao controlador principal.
A consulta HTTP permite ler o outro Raspberry sem misturar GPIOs dos dois dispositivos.

## Pinagem BCM
- SHT20: 3,3 V vermelho (pino 1), SDA GPIO2 amarelo (3), SCL GPIO3 branco (5), GND preto (posição a confirmar).
- Anel NeoPixel: dados GPIO18 preto (12), 5 V marrom (2/4), GND branco.
- Módulo de dois relés: 5 V azul (2/4), GND rosa; IN1 GPIO19 amarelo (35), IN2 GPIO26 verde (37).
- IN1 liga a fonte do conjunto ventoinha + resistência; IN2 reservado desligado.
- Câmera CSI conectada pelo cabo flat.

## Instalação no Raspberry da câmera
Use Raspberry Pi OS e o ambiente Python que já consegue acionar seu anel.
Ative I2C com sudo raspi-config. Picamera2 e GPIO Zero devem estar disponíveis:

```bash
sudo apt install python3-picamera2 python3-gpiozero python3-venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

Backend NeoPixel varia conforme o modelo do Raspberry. O driver escolhido segue seu
código anterior board.D18/NeoPixel; Raspberry Pi 5 pode exigir backend diferente.
Não executar dois processos controlando o mesmo GPIO18 simultaneamente.

Em config/config.json:
- remote_url: http://IP_DO_OUTRO_RASPBERRY:8080/sensors
- relay_active_low: true somente se confirmou LOW na placa de DOIS relés;
  false para HIGH. null bloqueia execução física. Teste com cargas desconectadas.
- led_count: 16 conforme código anterior; ajuste se o anel tiver outra quantidade.
- photo_interval: intervalo após término da captura, em segundos (1800 = 30 minutos).
- heating_enabled: false inicialmente; só habilitar após configurar política/limite térmico.

Use o MESMO token nos dois Raspberry, sem colá-lo em chats:

```bash
export CURING_TOKEN='substitua-por-um-segredo-local'
.venv/bin/python run_camera.py
```

Se o driver NeoPixel exigir root, use o ambiente correto e preserve apenas a variável
necessária com sudo --preserve-env=CURING_TOKEN .venv/bin/python run_camera.py.

## No outro Raspberry
Copiar a pasta completa do projeto e executar run_remote_server.py. O servidor de exemplo pressupõe um
segundo SHT20 no barramento 1/endereço 0x40. Se o outro sensor for diferente,
adapte read_sensor(). Não abra um segundo SMBus concorrente com o controlador
já existente: incorpore o cache/endpoint ao programa que faz a leitura.

```bash
export CURING_TOKEN='o-mesmo-segredo-local'
python3 run_remote_server.py
```

Porta TCP8080; endpoint GET /sensors. O servidor retorna temperature_c, humidity,
age_seconds e ok. Falha de aquisição invalida o cache; dados antigos não autorizam aquecimento.
HTTP/token é para rede local confiável; não publicar na internet. Permitir porta apenas
entre os Raspberry. Cliente não exige relógios sincronizados para verificar idade.

## Política de aquecimento desta versão
Fonte liga ventoinha e resistência JUNTAS. Não é possível pré/pós-ventilação independente.
O controle está desabilitado por padrão. Esta versão fornece uma política inicial por
UMIDADE DA CÁPSULA com histerese, NÃO garantia de prevenção de condensação:
- liga se UR local >= humidity_on;
- desliga se UR local <= humidity_off;
- desliga se leitura local/remota inválida ou antiga;
- temperatura local >= max_capsule_c desliga e trava até reiniciar após inspeção.
humidity_on=85 e humidity_off=75 são EXEMPLOS para ajuste, não valores validados.
Defina max_capsule_c conforme limites da câmera/eletrônica e testes térmicos e marque
humidity_policy_accepted=true apenas ao escolher essa política experimental.
Não inventamos um limite térmico apropriado para sua cápsula.

Dados remotos são consultados, registrados e exigidos válidos para autorizar fonte;
não são usados como alvo térmico do aquecedor. Pontos de orvalho dos dois ambientes
são calculados e registrados. Controle pela margem real ao ponto de orvalho pede
sensor de temperatura no acrílico e consideração das duas faces. Seu SHT20 mede o ar.
Termostato independente e proteção contra aquecimento sem fluxo continuam necessários.
GPIO/software não garantem desligamento em boot, travamento ou falha elétrica.

## Fotos e histórico
LED branco liga, espera estabilizar, câmera captura, LED desliga no finally.
Captura usa subprocesso com timeout de 15s; o laço do relé continua monitorando enquanto
sensores/rede são lidos em worker separado. Dados sem atualização por 10s desligam a fonte.
Sensor/rede têm trabalho serial, sem criar fila infinita. Sensor I2C travado impede novas
amostras e o watchdog do laço desliga. LED é desligado após término/timeout da captura.

Fotos reais: /home/rodrigueslucas/Pictures/images/low/ (configurável em photo_directory). Simulação: data/photos/simulation/. SQLite: data/camera.sqlite. Histórico inclui leituras em C/F, UR,
pontos de orvalho, motivo, erros e comandos dos relés; comandos não confirmam contatos físicos.
Foto recebe o snapshot do instante de recebimento do resultado (não leitura simultânea
à exposição). O campo snapshot_timing explicita essa limitação experimental.

```bash
python3 export_history.py
```

Gera data/history.csv separado por ponto e vírgula para Excel.

## Testar em computador sem hardware

```bash
python3 -m unittest discover -s tests -v
python3 run_camera.py --simulate --seconds 5
python3 export_history.py
```

Simulação cria arquivos .txt, nunca fotos fictícias em .jpg. Aquecimento simulado segue
a mesma configuração. Não há calibração de exposição/balanço de branco ou avaliação de
nitidez implementada; calibrar para imagens comparáveis às do treinamento.

## Referências
https://sensirion.com/sht20
https://docs.circuitpython.org/projects/neopixel/en/stable/examples.html
https://gpiozero.readthedocs.io/en/latest/api_output.html
https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

## Captura atualizada
Somente low: 640 × 480, formato BMP. AeEnable=false, AwbEnable=false,
ExposureTime=4000 µs, ColourGains=(1.15, 1.0), estabilização da câmera de 2 s.
Esses valores preservam o código fornecido, sem acrescentar ajuste de ganho analógico.
A repetição aguarda 30 minutos após cada rodada. Não execute o script antigo junto do novo.
