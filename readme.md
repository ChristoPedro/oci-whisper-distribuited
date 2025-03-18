# Whisper Dask - Processamento de Áudio Distribuído

Este projeto implementa um sistema distribuído de transcrição de áudio usando Whisper, Dask e serviços Oracle Cloud Infrastructure (OCI). Você pode escolher entre duas implementações:

- **Implementação Kafka**: Utiliza OCI Streaming (Kafka) para mensageria
- **Implementação Queue**: Utiliza OCI Queue para mensageria

> **Nota**: Escolha apenas uma das implementações de acordo com sua necessidade. Não é necessário implementar ambas.

## Arquitetura

O sistema possui dois modelos de implementação possíveis:

1. **Processador Kafka** - Consome mensagens do Kafka que contém referências a arquivos de áudio
2. **Processador Queue** - Consome mensagens da OCI Queue que contém referências a arquivos de áudio

Ambas implementações utilizam:

- Dask para processamento distribuído
- Faster Whisper para transcrição
- OCI Object Storage para armazenamento
- GPU NVIDIA para aceleração

## Pré-requisitos

- Kubernetes cluster com suporte a GPU NVIDIA
- Oracle Cloud Infrastructure (OCI) configurado
- Docker
- Python 3.12+
- CUDA 12.8.0

## Escolha sua Implementação

- [Implementação Kafka](./kafka/README.md)
- [Implementação Queue](./queue/README.md)

## Funcionamento

O sistema:

1. Consome mensagens (Kafka ou Queue) com referências a arquivos de áudio
2. Baixa os arquivos do OCI Object Storage
3. Processa usando Whisper com aceleração GPU
4. Salva as transcrições no bucket de saída
5. Utiliza Dask para processamento paralelo

## Características

- Processamento distribuído com Dask
- Aceleração GPU com CUDA
- Alta performance com faster-whisper
- Integração nativa com serviços OCI
- Logging detalhado de performance
- Configurável via ConfigMaps
- Containerizado com Docker

## Monitoramento

O sistema utiliza logging detalhado para monitorar:

- Tempo de download dos arquivos
- Tempo de carregamento do modelo
- Tempo de transcrição
- Tempo de upload
- Tempo total de processamento
