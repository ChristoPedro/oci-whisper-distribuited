from kafka import KafkaConsumer
import torch
from faster_whisper import WhisperModel
import json
import time
from io import BytesIO
from logger import logger
import oci
import os
import base64
from concurrent.futures import ThreadPoolExecutor

# Configurações da OCI

input_bucket_name = os.environ['INPUT_BUCKET_NAME']
output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']
region = os.environ['REGION']

signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

#Max de arquivos paralelos
max_parallel = int(os.environ['MAX_PARALLEL'])

# Kafka consumer
kafka_bootstrap_servers = os.environ['KAFKA_BOOTSTRAP_SERVERS']
kafka_topic = os.environ['KAFKA_TOPIC']
kafka_group_id = os.environ['KAFKA_GROUP_ID']
username = os.environ['KAFKA_USERNAME']
secret_ocid = os.environ['SECRET_OCID']

#Max de arquivos paralelos
max_parallel = int(os.environ['MAX_PARALLEL'])

# Carregando o modelo
model_name = 'large-v3'
model = WhisperModel(model_name, device="cuda", compute_type="float16", num_workers=5)
logger.info(f"Whisper model {model_name} loaded.")

# Criando CUDA streams 
streams = [torch.cuda.Stream() for _ in range(max_parallel)]

# Processamento único de mensagens
def process_message(message, stream):
    start = time.perf_counter()
    try:
        content = json.loads(message.content)
        object_name = content['data']['resourceName']

        # Autenticação to OCI Object Storage
        object_storage_client = oci.object_storage.ObjectStorageClient(
            config={}, signer=signer, 
            service_endpoint=f"https://objectstorage.{region}.oraclecloud.com"
        )
        namespace = object_storage_client.get_namespace().data

        # Download arquivo do Object Storage
        start_object = time.perf_counter()
        get_obj = object_storage_client.get_object(namespace, input_bucket_name, object_name)
        file_content = BytesIO(get_obj.data.content)
        logger.info(f"{object_name} - File downloaded in {time.perf_counter() - start_object:.2f} seconds.")
        
        # Trancição de audio usando stream
        transcription_options = dict(
            language='pt', beam_size=1, without_timestamps=False,
            word_timestamps=False, vad_filter=True, temperature=[0, 0.2, 0.4, 0.6, 0.8, 1],
            patience=1, no_speech_threshold=0.5, log_prob_threshold=-1,
            repetition_penalty=1, no_repeat_ngram_size=0
        )

        with torch.cuda.stream(stream):
            start_transc = time.perf_counter()
            segments, _ = model.transcribe(file_content, **transcription_options)
            transcription = " ".join(segment.text for segment in segments)
            logger.info(f"{object_name} - Transcription done in {time.perf_counter() - start_transc:.2f} seconds.")

        # Salva trancrição no OCI Object Storage
        start_upload = time.perf_counter()
        output_object_name = f'transcriptions/{object_name}.txt'
        object_storage_client.put_object(
            namespace, output_bucket_name, output_object_name, transcription
        )
        logger.info(f"{object_name} - Upload completed in {time.perf_counter() - start_upload:.2f} seconds.")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
    
    logger.info(f"{object_name} - Processing completed in {time.perf_counter() - start:.2f} seconds.") 

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

       
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            for i, message in enumerate(messages[:max_parallel]):
                executor.submit(process_message, message, streams[i])


if __name__ == "__main__":
    main()