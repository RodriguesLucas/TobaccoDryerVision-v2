"""Arquiteturas e pré-processamento iguais aos do treinador do TobaccoDryerVision-V3.

Só é importado quando há modelo de talo configurado e o torch está instalado.
No Raspberry Pi 3B+ (906 MB) prefira uma arquitetura leve, como mobilenet_v3_large.
"""


def construir_modelo(nome, quantidade_classes):
    from torch import nn
    from torchvision import models

    if nome not in ('resnet18', 'regnet_y_800mf', 'mobilenet_v3_small', 'mobilenet_v3_large',
                    'efficientnet_b0', 'efficientnet_v2_s'):
        raise ValueError(f'Arquitetura nao suportada: {nome}')
    modelo = getattr(models, nome)(weights=None)
    if nome in ('resnet18', 'regnet_y_800mf'):
        modelo.fc = nn.Linear(modelo.fc.in_features, quantidade_classes)
    elif nome.startswith('mobilenet'):
        modelo.classifier[3] = nn.Linear(modelo.classifier[3].in_features, quantidade_classes)
    else:
        modelo.classifier[1] = nn.Linear(modelo.classifier[1].in_features, quantidade_classes)
    return modelo


def criar_transformacao(tamanho_imagem):
    from torchvision import transforms

    return transforms.Compose([
        transforms.Resize((tamanho_imagem, tamanho_imagem)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
