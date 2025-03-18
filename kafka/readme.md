# Implementação Kafka

## Configuração

### Configuração de Eventos OCI

1. Habilitar eventos no Input Bucket:
   - Acesse o console OCI > Object Storage > Buckets > [INPUT_BUCKET_NAME]
   - Na seção "Eventos", clique em "Criar Regra de Evento"
   - Configure:
     - Nome da regra: `audio-upload-kafka`
     - Tipo de evento: `Object Create`
     - Serviço de destino: `Streaming`
     - Stream: Selecione o stream configurado no Kafka

### Configurar IAM Policies

```bash
Allow dynamic-group [seu-dynamic-group] to use buckets in compartment [seu-compartimento] 
Allow dynamic-group [seu-dynamic-group] to use secret-family in compartment [seu-compartimento] where target.secret.id = '[seu-secret-ocid]'
Allow dynamic-group [seu-dynamic-group] to use stream-pull on stream-family in compartment [seu-compartimento]
```

### Criar Usuário Kafka e Secret

Username para o Kafka segue o formato:

```bash
[tenancyName]/[UserName]/[Stream-Pool-OCID]
```

#### Criar Secret para Auth Token

1. No Console OCI, navegue até Security > Vault
2. Selecione ou crie um vault
3. Clique em "Create Secret"
4. Preencha:
   - Nome do Secret
   - Description (opcional)
   - Encryption Key: Selecione uma chave existente ou crie uma nova
   - Secret Type Template: Plain Text
   - Secret Contents: Cole o Auth Token do usuário Kafka
5. Anote o OCID do Secret criado (será usado no ConfigMap)

### Variáveis de Ambiente

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

## Deploy

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
