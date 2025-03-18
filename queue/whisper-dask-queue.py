import os
from faster_whisper import WhisperModel
from dask import delayed
from dask.distributed import Client
import dask
import json
import time
from io import BytesIO
from logger import logger
import oci


# Configurações da OCI

service_endpoint = os.environ['SERVICE_ENDPOINT']
queue_id = os.environ['QUEUE_ID']
region = os.environ['REGION']
input_bucket_name = os.environ['INPUT_BUCKET_NAME']
output_bucket_name = os.environ['OUTPUT_BUCKET_NAME']

# Função para processar uma única mensagem
def process_message(message):
    start = time.perf_counter()
    try:
        # Extrair o nome do arquivo da mensagem
        content = json.loads(message.content)

        # Fazer auth para Object Storage
        start_object = time.perf_counter()
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        object_storage_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer, service_endpoint=f"https://objectstorage.{region}.oraclecloud.com")
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

        delete_message(message)

    except Exception as e:
        print(f"Erro ao processar a mensagem: {e}")
    
    logger.info(f"{object_name} - Arquivo processado em {time.perf_counter() - start:.2f} seconds." )

def delete_message(messages):
    
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    queue_client = oci.queue.QueueClient(config={}, signer=signer, service_endpoint=service_endpoint)
    delete_message_response = queue_client.delete_message(
    queue_id=queue_id,
    message_receipt=messages.receipt)
    return delete_message_response.headers

def get_message():

    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    queue_client = oci.queue.QueueClient(config={}, signer=signer, service_endpoint=service_endpoint)
    get_messages_response = queue_client.get_messages(
        queue_id=queue_id,
        visibility_in_seconds=120,
        timeout_in_seconds=10,
        limit=5)
    return get_messages_response.data.messages
        
# Função principal para ler mensagens do queue e processá-las em paralelo
def main():

    Client(n_workers=5)

    while True:
        messages = get_message()
        if not messages:
            time.sleep(5)  # Wait for new messages
            continue
        tarefas = [delayed(process_message)(message) for message in messages]
        dask.compute(*tarefas)
   
if __name__ == "__main__":
    main()