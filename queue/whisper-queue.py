import os
import torch
from faster_whisper import WhisperModel
import json
import time
from io import BytesIO
from logger import logger
import oci
from concurrent.futures import ThreadPoolExecutor

# Configuração do OCI
service_endpoint = os.environ['SERVICE_ENDPOINT']
queue_id = os.environ['QUEUE_ID']
region = os.environ['REGION']
input_bucket_name = os.environ['INPUT_BUCKET_NAME']
output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']

signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

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

        delete_message(message)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
    
    logger.info(f"{object_name} - Processing completed in {time.perf_counter() - start:.2f} seconds.")

# Deleta Mensagem processada da fila
def delete_message(message):
    queue_client = oci.queue.QueueClient(config={}, signer=signer, service_endpoint=service_endpoint)
    queue_client.delete_message(queue_id=queue_id, message_receipt=message.receipt)

# Retona mensagens da fila
def get_messages():
    queue_client = oci.queue.QueueClient(config={}, signer=signer, service_endpoint=service_endpoint)
    return queue_client.get_messages(queue_id=queue_id, visibility_in_seconds=120, timeout_in_seconds=10, limit=max_parallel).data.messages

# Main function
def main():
    while True:
        messages = get_messages()
        if not messages:
            time.sleep(5)  # Espera por novas mensagens
            continue
        
        # Processa mensagens em paralelo
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            for i, message in enumerate(messages[:max_parallel]):
                executor.submit(process_message, message, streams[i])

if __name__ == "__main__":
    main()
