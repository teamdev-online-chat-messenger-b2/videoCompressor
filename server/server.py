import socket
import os
import json
import uuid
import subprocess
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class SuccessInfo:
    def __init__(self, filepath, file_size) -> None:
        self.filepath = filepath
        self.file_size = file_size

    @property
    def file_extension(self):
        return os.path.splitext(self.filepath)[1].lstrip('.')

    def to_dict(self):
        return {
            'status_code': 'success',
            'file_extension': self.file_extension,
            'file_size': self.file_size
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

class ErrorInfo:
    def __init__(self, code, description, solution) -> None:
        self.error_code = code
        self.description = description
        self.solution = solution

    def to_dict(self):
        return {
            'error_code': self.error_code,
            'description': self.description,
            'solution': self.solution
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

# コネクション関連の関数はここから実装
def create_server_socket(config):
    # アドレスファミリ : socket.AF_INET, 通信方式 : SOCK_STREAM = TCP通信（信頼性あり、順番保証、コネクション型）
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((config['server_address'], config['server_port']))
    sock.listen(1)
    print('サーバーが起動します。クライアントからの接続を待ちます。')
    return sock

# リクエストに関係する関数はここから実装
def initialize_rsa():
    global global_rsa_manager
    global_rsa_manager = RSAManager()
    print("RSA鍵を生成")

def exchange_public_keys(connection):
    try:
        # RSA公開鍵の取得（鍵の長さ（４バイト）、鍵）
        client_public_key_length = int.from_bytes(connection.recv(4), 'big')
        client_public_key_pem = connection.recv(client_public_key_length).decode('utf-8')
        client_public_key = serialization.load_pem_public_key(client_public_key_pem.encode())
        print("クライアントの公開鍵をロード完了")

        # クライアントのPEMフォーマットの公開鍵
        server_public_key_pem = global_rsa_manager.generatePublicKeyPem()

        connection.send(len(server_public_key_pem).to_bytes(4, 'big'))
        connection.send(server_public_key_pem)
        print("サーバーの公開鍵を送信完了")

        if isinstance(client_public_key, rsa.RSAPublicKey):
            print("公開鍵の交換完了")
            return client_public_key
        else:
            raise TypeError("クライアントの公開鍵はRSAフォーマットではありません")

    except Exception as e:
        print(f"公開鍵の交換に失敗：{e}")
        raise

def receive_encrypted_aes_key(connection):
    try:
        encrypted_aes_key_size = int.from_bytes(connection.recv(4), 'big')
        encrypted_aes_key = connection.recv(encrypted_aes_key_size)
        if len(encrypted_aes_key) != encrypted_aes_key_size:
            raise Exception("受信したAES鍵が期待する長さを満たしません")
        
        decrypted_aes_key = global_rsa_manager.decryptContent(encrypted_aes_key)
        
        return decrypted_aes_key
    
    except Exception as e:
        print(f"暗号化されたAES鍵の受信に失敗：{e}")
        raise

def decrypt_chunk(encrypted_chunk, aes_key):
    try:
        nonce = encrypted_chunk[:12]

        auth_tag = encrypted_chunk[-16:]

        encrypted_data = encrypted_chunk[12:-16]

        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(nonce, auth_tag),
            backend=default_backend()
        )

        decryptor = cipher.decryptor()

        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        return decrypted_data
    
    except Exception as e:
        print(f"AES暗号化されたメッセージの解読に失敗：{e}")
        raise

def encrypt_chunk(chunk, aes_key):
    try:
        nonce = os.urandom(12)

        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(nonce),
            default_backend()
        )
        encryptor = cipher.encryptor()

        encrypted_chunk = encryptor.update(chunk) + encryptor.finalize()

        auth_tag = encryptor.tag

        return nonce + encrypted_chunk + auth_tag
    
    except Exception as e:
        print(f"AES暗号化に失敗：{e}")
        raise


def handle_client_request(config, connection):
    client_public_key = exchange_public_keys(connection)
    aes_key = receive_encrypted_aes_key(connection)

    # AESによって暗号化されたヘッダー（３６バイト）、解読されたヘッダー（８バイト）の中にある、JSONサイズ（２バイト）、メディアタイプ（１バイト）、ファイルサイズ（５バイト）
    encrypted_header = connection.recv(8 + 12 + 16)
    decrypted_header = decrypt_chunk(encrypted_header, aes_key)
    json_size = int.from_bytes(decrypted_header[:2], 'big')
    mediatype_size = int.from_bytes(decrypted_header[2:3], 'big')
    file_size = int.from_bytes(decrypted_header[3:], 'big')

    # ファイルサイズが0の場合はエラーとして扱う
    if file_size <= 0:
        raise Exception('ファイルサイズが無効です')
    
    encrypted_req_params = connection.recv(json_size + 12 + 16)
    decrypted_req_params = decrypt_chunk(encrypted_req_params, aes_key).decode('utf-8')
    encrypted_mediatype = connection.recv(mediatype_size + 12 + 16)
    decrypted_mediatype = decrypt_chunk(encrypted_mediatype, aes_key).decode('utf-8')

    filename = f'{uuid.uuid4().hex}.{decrypted_mediatype}'

    upload_error = store_uploaded_file_encrypted(config, connection, filename, file_size, aes_key)

    if upload_error is not None:
        return upload_error, aes_key

    req_data = json.loads(decrypted_req_params)
    action = req_data.get('action', 0)

    print(f"受信したアクション: {action}")

    match action:
        case 1:
            try:
                processed_filename, output_path = compress_video(filename, config['dir_path'])
                print(f'動画圧縮完了: {processed_filename}')
                error = send_encrypted_response(connection, output_path, config['stream_rate'], aes_key)

                if error is not None:
                    return error, aes_key
            except Exception as process_err:
                error = ErrorInfo('1002', f'動画圧縮中のエラー: {str(process_err)}', 'FFMPEGが正しくインストールされているか確認してください。')
                print(f"圧縮処理エラー: {str(process_err)}")
                return error, aes_key
        case 2:
            try:
                processed_filename, output_path = handle_resolution_change(filename, config['dir_path'], req_data)
                print(f'解像度変更完了: {processed_filename}')
                error  = send_encrypted_response(connection, output_path, config['stream_rate'], aes_key)

                if error is not None:
                    return error, aes_key

            except Exception as process_err:
                error = ErrorInfo('1003', f'動画処理中のエラー: {str(process_err)}', 'FFMPEGが正しくインストールされているか確認してください。')
                print(f"解像度処理エラー: {str(process_err)}")
                return error, aes_key
        case 3:
            try:
                processed_filename, output_path = handle_aspect_change(filename, config['dir_path'], req_data)
                print(f'アスペクト比変更完了: {processed_filename}')
                error = send_encrypted_response(connection, output_path, config['stream_rate'], aes_key)

                if error is not None:
                    return error, aes_key

            except Exception as process_err:
                error = ErrorInfo('1004', f'動画のアスペクト比変更中のエラー: {str(process_err)}', 'アップロード動画を確認し再度アップロードおよび操作をしてください、解決しない場合は管理者にお問い合わせください。')
                print(f"処理エラー: {str(process_err)}")
                return error, aes_key
        case 4:
            try:
                processed_filename, output_path = handle_video_conversion(filename, config['dir_path'])
                print(f'オーディオへの変換完了: {processed_filename}')
                error  = send_encrypted_response(connection, output_path, config['stream_rate'], aes_key)

                if error is not None:
                    return error, aes_key

            except Exception as process_err:
                error = ErrorInfo('1005', f'オーディオへの変換中のエラー: {str(process_err)}', 'アップロード動画を確認し再度アップロードおよび操作をしてください、解決しない場合は管理者にお問い合わせください。')
                print(f"オーディオへの変換中のエラー: {str(process_err)}")
                return error, aes_key
        case 5:
                filepath = os.path.join(config['dir_path'], filename)
                error = validate_video_duration(filepath,req_data.get('endseconds'))
                if error != None:
                    return error, aes_key
                
                try:
                    processed_filename,output_path = handle_process_video_clip(filename, config['dir_path'], req_data)
                    print(f'時間範囲での動画を作成完了: {processed_filename}')
                    send_encrypted_response(connection, output_path, config['stream_rate'], aes_key)

                except Exception as process_err:
                    error = ErrorInfo('1006', f'動画処理中のエラー: {str(process_err)}', 'アップロードした動画を再度確認し、再度トライしてください。')
                    print(f"処理エラー: {str(process_err)}")
                    return error, aes_key

    inputfile_path = os.path.join(config['dir_path'], filename)
    delete_tmp_files([inputfile_path, output_path])

    return None, aes_key

def store_uploaded_file_encrypted(config, connection, filename, original_file_size, aes_key):
    try:
        with open(os.path.join(config['dir_path'], filename), 'wb+') as f:
            total_received = 0
            
            while total_received < original_file_size:
                remaining = original_file_size - total_received

                chunk_size = min(config['stream_rate'], remaining)
                encrypted_chunk_size = chunk_size + 12 + 16

                encrypted_chunk = b''
                while len(encrypted_chunk) < encrypted_chunk_size:
                    data = connection.recv(encrypted_chunk_size - len(encrypted_chunk))
                    if not data:
                        raise Exception("Connection closed unexpectedly")
                    encrypted_chunk += data

                decrypted_chunk = decrypt_chunk(encrypted_chunk, aes_key)

                actual_chunk_size = min(len(decrypted_chunk), remaining)
                f.write(decrypted_chunk[:actual_chunk_size])
                total_received += actual_chunk_size

        print('ファイルのアップロードが完了しました。')
        return None

    except Exception as file_err:
        print(f"File storage error: {file_err}")
        try:
            remaining = original_file_size - total_received
            while remaining > 0:
                chunk_size = min(config['stream_rate'] + 28, remaining)
                connection.recv(chunk_size)
                remaining -= (chunk_size - 28)
        except:
            pass
            
        error = ErrorInfo('1001', 'ファイル保存中のエラー:' + str(file_err), '解決しない場合は管理者にお問い合わせください。')
        return error

# レスポンスに関係する関数はここから実装
def send_encrypted_response(connection, filepath, stream_rate, aes_key):
    # 各処理後にプロセス後のデータを含むレスポンスをクライアントに返す関数
    try:
        with open(filepath, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            f.seek(0, 0)

            # サクセスコード：１（１バイト)とファイルサイズ（８バイト）
            success_header = b'\x01'
            encrypted_header = encrypt_chunk(success_header, aes_key)

            connection.send(len(encrypted_header).to_bytes(4, 'big'))
            connection.sendall(encrypted_header)

            success_json = SuccessInfo(filepath, file_size).to_json()
            success_bytes = success_json.encode('utf-8')
            encrypted_json = encrypt_chunk(success_bytes, aes_key)

            connection.send(len(encrypted_json).to_bytes(4, 'big'))
            connection.sendall(encrypted_json)

            print(f"処理済みファイル（{file_size}バイト）を送信中")

            # ファイルをstream_rateサイズに分割して送る
            total_sent = 0
            while total_sent < file_size:
                data = f.read(stream_rate)
                if not data:
                    break

                encrypted_chunk = encrypt_chunk(data, aes_key)

                connection.send(len(encrypted_chunk).to_bytes(4, 'big'))
                connection.send(encrypted_chunk)

                total_sent += len(data)

            print("処理済みファイルの送信完了")
            return None

    except Exception as error:
        print(f"ファイル送信エラー: {str(error)}")
        return ErrorInfo('1004', f'ファイル送信エラー: {str(error)}', 'ネットワーク接続を確認してください。')

def send_encrypted_error_response(connection, error_info, aes_key):
    # エラーレスポンスをクライアントに返す関数
    try:
        # エラーコード：０（１バイト）とエラーJSON（ErrorInfoオブジェクト）を共にAES暗号化し、データサイズとデータを送信
        error_header = b'\x00'
        encrypted_header = encrypt_chunk(error_header, aes_key)
        connection.send(len(encrypted_header).to_bytes(4, 'big'))
        connection.sendall(encrypted_header)

        error_json = error_info.to_json()
        error_bytes = error_json.encode('utf-8')
        encrypted_json = encrypt_chunk(error_bytes, aes_key)
        connection.send(len(encrypted_json).to_bytes(4, 'big'))
        connection.sendall(encrypted_json)

        print(f"暗号化されたエラーレスポンス送信: {error_info.error_code}")

    except Exception as error:
        print(f"暗号化エラーレスポンス送信失敗: {str(error)}")

# その他必要な関数はここから実装
def load_server_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    return {
        'server_address': config['server_address'],
        'server_port': config['server_port'],
        'max_storage': config['max_storage'],
        'dir_path': BASE_DIR + config['storage_dir'],
        'stream_rate': config['stream_rate']
    }

def delete_tmp_files(file_paths_to_delete:list):
    """指定されたパスのファイルを削除する関数"""
    for file_path in file_paths_to_delete:
        try:
            os.remove(file_path)
            print(f"ファイル {file_path} を削除しました")
        except FileNotFoundError:
            print(f"ファイル {file_path} が見つかりません")
        except PermissionError:
            print(f"ファイル {file_path} の削除権限がありません")
        except Exception as e:
            print(f"ファイル {file_path} の削除に失敗: {e}")

class RSAManager:
    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent = 65537,
            key_size = 2048
        )
        self.public_key = self.private_key.public_key()

    def generatePublicKeyPem(self) -> bytes:
        pem_bytes = self.public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_bytes

    def decryptContent(self, content) -> bytes:
        decrypted_bytes = self.private_key.decrypt(
            content,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted_bytes

# 動画圧縮に関する関数はここから実装
def compress_video(input_filename, dir_path):
    input_path = os.path.join(dir_path, input_filename)
    base_name = input_filename.split('.')[0]
    output_filename = f"{base_name}_compressed.mp4"
    output_path = os.path.join(dir_path, output_filename)

    # 入力ファイルのサイズ取得(MB)
    input_file_size = os.path.getsize(input_path) / (1024 * 1024)

    # 圧縮率を動的に決定
    if input_file_size > 300:
        preset = 'slow'
    elif input_file_size > 100:
        preset = 'medium'
    else:
        preset = 'fast'

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-vcodec', 'libx264',  # 動画コーデック
        '-crf', '28',           # 圧縮率
        '-preset', preset,     # エンコード速度
        '-c:a', 'copy',        # 音声はコピー
        output_path
    ]

    print(f"FFMPEG実行中: {' '.join(ffmpeg_cmd)}")

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=False)
    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")

    return output_filename, output_path

# 動画解像度などの機能的な関数はここから実装
def handle_resolution_change(input_filename, dir_path, req_data):
    chosen_resolution = req_data.get('resolution', 0)

    input_path = os.path.join(dir_path, input_filename)
    base_name = input_filename.split('.')[0]
    output_filename = f"{base_name}_{chosen_resolution}.mp4"
    output_path = os.path.join(dir_path, output_filename)

    resolution_choices = {
        "480p": (854, 480),
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "1440p": (2560, 1440),
        "4K": (3840, 2160)
    }

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-vf', f'scale={resolution_choices[chosen_resolution][0]}:{resolution_choices[chosen_resolution][1]}',
        '-c:a', 'copy',
        '-preset', 'fast',
        output_path
    ]

    print(f"FFMPEG実行中: {' '.join(ffmpeg_cmd)}")

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=False)
    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")
    return output_filename, output_path

# 動画アスペクト比処理に関する関数はここから実装
def handle_aspect_change(input_filename, dir_path, req_data):
    chosen_aspect_ratio = req_data.get('aspect_ratio', 0)

    input_path = os.path.join(dir_path, input_filename)
    base_name = input_filename.split('.')[0]
    output_filename = f"{base_name}_{chosen_aspect_ratio}.mp4"
    output_path = os.path.join(dir_path, output_filename)

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-aspect', chosen_aspect_ratio,  # アスペクト比を設定
        '-c:v', 'libx264',              # 動画コーデック
        '-c:a', 'copy',                 # 音声はコピー
        '-preset', 'ultrafast',
        output_path
    ]

    print(f"FFMPEG実行中: {' '.join(ffmpeg_cmd)}")

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=False)
    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")

    return output_filename, output_path

# 音声への変換処理に関する関数はここから実装
def handle_video_conversion(input_filename, dir_path):
    input_path = os.path.join(dir_path, input_filename)
    base_name = input_filename.split('.')[0]
    output_filename = f"{base_name}_audio.mp3"
    output_path = os.path.join(dir_path, output_filename)

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-vn',
        '-acodec', 'mp3',
        '-ab', '192k',
        '-ar', '44100',
        '-ac', '2',
        output_path
    ]

    print(f"FFMPEG実行中: {' '.join(ffmpeg_cmd)}")

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=False)
    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")
    return output_filename, output_path

# GIFとWEBMへの変換処理に関する関数はここから実装
def handle_process_video_clip(input_filename:str, dir_path:str, req_data:dict):
    chosen_extension = req_data.get('extension')
    startseconds = req_data.get('startseconds')
    endseconds = req_data.get('endseconds')
    input_path = os.path.join(dir_path, input_filename)
    base_name = input_filename.split('.')[0]
    output_filename = f"{base_name}.{chosen_extension}"
    output_path = os.path.join(dir_path, output_filename)

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-ss', str(startseconds),
        '-to', str(endseconds),
        output_path
    ]

    print(f"FFMPEG実行中: {' '.join(ffmpeg_cmd)}")

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=False)
    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")
    return output_filename, output_path

def get_video_duration(filepath:str):
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',  # ヘッダーなしで数値のみ
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True)

    return float(result.stdout)

def validate_video_duration(filepath:str, endseconds:int) -> ErrorInfo | None:
    duration_seconds = get_video_duration(filepath)
    error_info = None
    if duration_seconds < endseconds:
        error_info = ErrorInfo('1007', '指定した終了時刻が動画の長さを超えています', '指定範囲は動画の時間を超えない値で設定してください')
        print('指定した終了時刻が動画の長さを超えています。処理を終了します')
    return error_info

# メイン（エントリーポイント）
def main():
    initialize_rsa()

    config = load_server_config()
    sock = create_server_socket(config)

    while True:
        connection, client_address = sock.accept()
        print(f'{client_address}と接続しました。')

        error = None
        aes_key = None

        try:
            error, aes_key = handle_client_request(config, connection)

        except Exception as e:
            error = ErrorInfo('1002', str(e), '解決しない場合は管理者にお問い合わせください。')

        finally:
            if error is not None:
                print(error.to_json())
                if aes_key is not None:
                    send_encrypted_error_response(connection, error, aes_key)
                else:
                    print("AES鍵が利用できないため、暗号化されていないエラーレスポンスを送信できません")

            print('コネクションを閉じます')
            connection.close()

if __name__ == '__main__':
    main()
