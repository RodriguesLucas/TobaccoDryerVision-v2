# Raspberry da câmera — SHT20

Projeto organizado por função. Instruções completas: docs/INSTALACAO.md.

| Caminho | Responsabilidade |
|---|---|
| config/config.json | Pinos lógicos, parâmetros, URL remota e aquecimento |
| src/app.py | Coordenação das tarefas e laço principal |
| src/camera/photo_worker.py | Sequência de iluminação e captura |
| src/control/hardware.py | Saídas físicas dos relés e LED |
| src/communication/remote_client.py | Consulta às leituras remotas |
| src/storage/history.py | Gravação dos eventos no SQLite |
| src/sensors/sht20.py | Leitura I²C com CRC |
| src/camera/capture_once.py | Captura CSI com Picamera2 |
| src/control/logic.py | Histerese, validação e proteção térmica |
| src/communication/remote_server.py | Servidor de leituras no outro Raspberry |
| src/storage/export_csv.py | Exportação do histórico |
| tests/ | Testes da lógica |
| data/photos/ | Fotografias geradas durante execução |
| docs/ | Instalação, pinagem e limites desta versão |

O LED e os relés são inicializados em src/control/hardware.py. Esta reorganização mantém
as funcionalidades do pacote anterior; não acrescenta IA ou controle do flap.

Execute na pasta principal:

```bash
python3 -m unittest discover -s tests -v
python3 run_camera.py --simulate --seconds 10
```

Na câmera, após configurar os parâmetros e dependências:

```bash
export CURING_TOKEN='seu-segredo-local'
.venv/bin/python run_camera.py
```

No outro Raspberry, usando o mesmo token:

```bash
export CURING_TOKEN='seu-segredo-local'
.venv/bin/python run_remote_server.py
```

Exportar dados:

```bash
python3 export_history.py
```

Aquecimento desabilitado inicialmente; polaridade dos relés a confirmar.
Configuração, fotos e banco SQLite usam caminhos relativos à pasta do projeto,
independentemente da pasta de onde o comando é executado.

Código, nomes de métodos, variáveis e campos JSON permanecem em inglês.
Comentários, documentação, mensagens do terminal e cabeçalhos CSV estão em português.
Consulte docs/METODOS.md para entender o fluxo do programa.
