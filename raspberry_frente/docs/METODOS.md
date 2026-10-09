# Guia dos métodos

| Método | Objetivo |
|---|---|
| load_configuration | Carregar e verificar os parâmetros antes de acessar hardware |
| collect_samples | Ler os sensores local e remoto sem bloquear o controlador |
| samples_are_fresh | Impedir uso de leituras antigas |
| HeatingController.update | Decidir a demanda da fonte com histerese e proteção térmica |
| CameraHardware.set_power | Aplicar o comando ao relé 1 |
| CameraHardware.set_light | Acender/apagar o anel LED |
| capture_photos | Executar a sequência de iluminação e fotografia |
| capture_image | Configurar Picamera2 e salvar uma fotografia |
| build_snapshot | Preparar os dados para monitoramento e histórico |
| record_photo_events | Registrar a fotografia junto do estado disponível |
| HistoryStore.save | Gravar um evento no banco SQLite |
| read_remote_sample | Consultar o outro Raspberry com timeout e validação |
| acquire_samples | Atualizar o cache do servidor remoto |
| run_control_loop | Monitorar continuamente e aplicar os comandos |

A aquisição e a captura executam em threads separadas. O laço principal controla
a fonte e grava o histórico. A câmera executa em subprocesso com timeout.
Os arquivos usam docstrings em português logo abaixo de cada método para explicar
seu objetivo. Comentários adicionais explicam decisões que não são óbvias pelo nome.
