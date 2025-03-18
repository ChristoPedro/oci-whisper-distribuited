from kafka import KafkaConsumer
from faster_whisper import WhisperModel
from dask import delayed
from dask.distributed import Client
import dask
import json
import time
from io import BytesIO
from logger import logger
import oci
import os

# Configurações da OCI

input_bucket_name = os.environ['INPUT_BUCKET_NAME']
output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']
region = os.environ['REGION']

# Kafka consumer
kafka_bootstrap_servers = os.environ['KAFKA_BOOTSTRAP_SERVERS']
kafka_topic = os.environ['KAFKA_TOPIC']
kafka_group_id = os.environ['KAFKA_GROUP_ID']
username = os.environ['KAFKA_USERNAME']
secret_ocid = os.environ['SECRET_OCID']

# Função para processar uma única mensagem
def process_message(message):
    start = time.perf_counter()
    try:
        # Extrair o nome do arquivo da mensagem
        content = json.loads(message.value.decode('utf-8'))

        start_object = time.perf_counter()
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        object_storage_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer, service_endpoint='https://objectstorage.sa-vinhedo-1.oraclecloud.com')
        namespace = object_storage_client.get_namespace().data

        # Baixar o arquivo do OCI Object Storage
        object_name = content['data']['resourceName']
        get_obj = object_storage_client.get_object(namespace, input_bucket_name, object_name,)
        file_content = BytesIO(get_obj.data.content)
        logger.info(f"{object_name} - Arquivo Baixado em {time.perf_counter() - start_object:.2f} seconds." )

        model_name = 'large-v3-turbo'
        start_model = time.perf_counter()
        model = WhisperModel(model_name, device="cuda", compute_type="float16", num_workers=5)
        logger.info(f"{object_name} - {model_name} loaded in {time.perf_counter() - start_model:.2f} seconds." )
        
        # Processa o arquivo usando whisper

        transcription_options = dict(
            language='pt',
            beam_size=1,
            without_timestamps=False,
            word_timestamps=False,
            vad_filter=True,
            temperature=[0, 0.2, 0.4, 0.6, 0.8, 1],
            patience=1,
            no_speech_threshold=0.5,
            log_prob_threshold=-1,
            repetition_penalty=1,
            no_repeat_ngram_size=0,
        )

        start_transc = time.perf_counter()
        segments, info = model.transcribe(file_content, **transcription_options)
        #segments = list(transcricao_gerador)
        transcription = " ".join(segment.text for segment in segments)
        logger.info(f"{object_name} - Transcrição feita em {time.perf_counter() - start_transc:.2f} seconds." )

        # Salvar a transcrição em outro bucket
        print('Salvando a transcrição:', object_name)
        start_upload = time.perf_counter()
        output_object_name = f'transcriptions/{object_name}.txt'
        object_storage_client.put_object(
            namespace,
            output_bucket_name,
            output_object_name,
            transcription
        )
        logger.info(f"{object_name} - Upload feito em {time.perf_counter() - start_upload:.2f} seconds." )

    except Exception as e:
        print(f"Erro ao processar a mensagem: {e}")
    fim = time.perf_counter_ns()
    logger.info(f"{object_name} - Arquivo processado em {time.perf_counter() - start:.2f} seconds." ) 

def get_text_secret(secret_ocid):
    try:
        client = oci.secrets.SecretsClient(config={}, signer=signer)
        secret_content = client.get_secret_bundle(secret_ocid).data.secret_bundle_content.content.encode('utf-8')
        decrypted_secret_content = base64.b64decode(secret_content).decode("utf-8")
    except Exception as ex:
        print("ERROR: failed to retrieve the secret content", ex, flush=True)
        raise
    return decrypted_secret_content
        
# Função principal para ler mensagens do stream e processá-las em paralelo
def main():

    Client(n_workers=5)

    consumer = KafkaConsumer(
        kafka_topic,
        bootstrap_servers=kafka_bootstrap_servers,
        group_id=kafka_group_id,
        security_protocol = 'SASL_SSL', sasl_mechanism = 'PLAIN',
        sasl_plain_username = username, 
        sasl_plain_password = get_text_secret(secret_ocid),
        auto_offset_reset='latest',  
        enable_auto_commit=True,
        max_poll_records=5
    )
   
    while True:
        
        messages = consumer.poll(timeout_ms=5000)  
        if not messages:
            time.sleep(5)  
            continue

       
        tarefas = []
        for topic_partition, msg_batch in messages.items():
            for message in msg_batch:
                tarefas.append(delayed(process_message)(message))
        
        dask.compute(*tarefas)


if __name__ == "__main__":
    main()