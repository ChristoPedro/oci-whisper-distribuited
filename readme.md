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

## Configuração

### Variáveis de Ambiente

#### Para Kafka

```yaml
INPUT_BUCKET_NAME: nome do bucket de entrada
OUTPUT_BUCKET_NAME: nome do bucket de saída
REGION: região OCI
KAFKA_BOOTSTRAP_SERVERS: servidores kafka
KAFKA_TOPIC: tópico kafka
KAFKA_GROUP_ID: id do grupo consumer
KAFKA_USERNAME: usuário kafka
SECRET_OCID: OCID do secret
```

#### Para Queue

```yaml
INPUT_BUCKET_NAME: nome do bucket de entrada
OUTPUT_BUCKET_NAME: nome do bucket de saída
REGION: região OCI
SERVICE_ENDPOINT: endpoint da OCI Queue
QUEUE_ID: id da queue
```

## Configuração de Eventos OCI

### Configuração para Kafka

1. Habilitar eventos no Input Bucket:
   - Acesse o console OCI > Object Storage > Buckets > [INPUT_BUCKET_NAME]
   - Na seção "Eventos", clique em "Criar Regra de Evento"
   - Configure:
     - Nome da regra: `audio-upload-kafka`
     - Tipo de evento: `Object Create`
     - Serviço de destino: `Streaming`
     - Stream: Selecione o stream configurado no Kafka

### Configuração para Queue

1. Habilitar eventos no Input Bucket:
   - Acesse o console OCI > Object Storage > Buckets > [INPUT_BUCKET_NAME]
   - Na seção "Eventos", clique em "Criar Regra de Evento"
   - Configure:
     - Nome da regra: `audio-upload-queue`
     - Tipo de evento: `Object Create`
     - Serviço de destino: `Functions`
     - Function: Selecione a function criada com [fnqueueproducer](https://github.com/ChristoPedro/fnqueueproducer)

2. Deploy da Function Produtora:
   - Clone o repositório fnqueueproducer:

   ```bash
   git clone https://github.com/ChristoPedro/fnqueueproducer.git
   ```

   - Configure as variáveis de ambiente da function:

   ```yaml
   QUEUE_ID: id da queue
   ENDPOINT: endpoint da OCI Queue
   ```

   - Deploy da function seguindo as instruções do repositório

Após estas configurações, quando um arquivo de áudio for enviado para o INPUT_BUCKET:

- Na implementação Kafka: Uma mensagem será publicada automaticamente no OCI Stream
- Na implementação Queue: A function será acionada e publicará a mensagem na OCI Queue

## Instalação

Escolha apenas uma das implementações abaixo:

### Para implementação Kafka

1. Build da imagem Docker:

    ```bash
    cd kafka
    docker build -t [Sua-Imagem-Docker] .
    ```

2. Configure os manifestos Kubernetes:

    Atualize o `config-map.yaml`:

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
    name: kafka-config
    data:
    INPUT_BUCKET_NAME: "seu-bucket-entrada"
    OUTPUT_BUCKET_NAME: "seu-bucket-saida"
    REGION: "sua-regiao"
    KAFKA_BOOTSTRAP_SERVERS: "seus-servidores"
    KAFKA_TOPIC: "seu-topico"
    KAFKA_GROUP_ID: "seu-grupo"
    KAFKA_USERNAME: "seu-usuario"
    SECRET_OCID: "seu-secret-ocid"
    ```

    Atualize o `deployment.yaml` com sua imagem Docker:

    ```yaml
    spec:
    template:
        spec:
        containers:
        - name: kafka-processor
            image: [Sua-Imagem-Docker]
    ```

3. Deploy no Kubernetes:

    ```bash
    kubectl apply -f kafka/config-map.yaml
    kubectl apply -f kafka/deployment.yaml
    ```

### Para implementação Queue

1. Build da imagem Docker:

    ```bash
    cd queue
    docker build -t [Sua-Imagem-Docker] .
    ```

2. Configure os manifestos Kubernetes:

    Atualize o `config-map.yaml`:

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
    name: queue-config
    data:
    INPUT_BUCKET_NAME: "seu-bucket-entrada"
    OUTPUT_BUCKET_NAME: "seu-bucket-saida"
    REGION: "sua-regiao"
    SERVICE_ENDPOINT: "seu-endpoint"
    QUEUE_ID: "seu-queue-id"
    ```

    Atualize o `deployment.yaml` com sua imagem Docker:

    ```yaml
    spec:
    template:
        spec:
        containers:
        - name: queue-processor
            image: [Sua-Imagem-Docker]
    ```

3. Deploy no Kubernetes:

    ```bash
    kubectl apply -f queue/config-map.yaml
    kubectl apply -f queue/deployment.yaml
    ```

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
