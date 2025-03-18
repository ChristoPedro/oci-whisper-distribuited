# Implementação Queue

## Configuração

### Configuração de Eventos OCI

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

### Configurar IAM Policies

```bash
Allow dynamic-group [seu-dynamic-group] to use buckets in compartment [seu-compartimento] 
Allow dynamic-group [seu-dynamic-group] to use queues in compartment [seu-compartimento]
```

### Variáveis de Ambiente

```yaml
INPUT_BUCKET_NAME: nome do bucket de entrada
OUTPUT_BUCKET_NAME: nome do bucket de saída
REGION: região OCI
SERVICE_ENDPOINT: endpoint da OCI Queue
QUEUE_ID: id da queue
```

## Deploy

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
