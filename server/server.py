import socket
import os
import json
import uuid
import subprocess

class ErrorInfo:
    def __init__(self,code, description, solution) -> None:
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
def handle_client_request(config, connection):
    # ヘッダー（８バイト）の中にある、JSONサイズ（２バイト）、メディアタイプ（１バイト）、ファイルサイズ（５バイト）
    header = connection.recv(8)
    json_size = int.from_bytes(header[:2], 'big')
    mediatype_size = int.from_bytes(header[2:3], 'big')
    file_size = int.from_bytes(header[3:], 'big')

    # ファイルサイズが0の場合はエラーとして扱う
    if file_size <= 0:
        raise Exception('ファイルサイズが無効です')

    req_params = connection.recv(json_size).decode('utf-8')
    mediatype = connection.recv(mediatype_size).decode('utf-8')

    filename = f'{uuid.uuid4().hex}.{mediatype}'

    upload_error = store_uploaded_file(config, connection, filename, file_size)

    if upload_error is not None:
        return upload_error

    req_data = json.loads(req_params)
    action = req_data.get('action', 0)

    print(f"受信したアクション: {action}")

    match action:
        case 1:
            pass
        case 2:
            try:
                processed_filename, output_path = handle_resolution_change(filename, config['dir_path'], req_data)
                print(f'解像度変更完了: {processed_filename}')
                error  = send_response(connection, output_path, config['stream_rate'])

                if error is not None:
                    return error

            except Exception as process_err:
                error = ErrorInfo('1003', f'動画処理中のエラー: {str(process_err)}', 'FFMPEGが正しくインストールされているか確認してください。')
                print(f"解像度処理エラー: {str(process_err)}")
                return error
        case 3:
            try:
                processed_filename, output_path = handle_aspect_change(filename, config['dir_path'], req_data)
                print(f'アスペクト比変更完了: {processed_filename}')
                error = send_response(connection, output_path, config['stream_rate'])

                if error is not None:
                    return error

            except Exception as process_err:
                error = ErrorInfo('1004', f'動画のアスペクト比変更中のエラー: {str(process_err)}', 'アップロード動画を確認し再度アップロードおよび操作をしてください、解決しない場合は管理者にお問い合わせください。')
                print(f"処理エラー: {str(process_err)}")
                return error
        case 4:
            pass
        case 5:
            pass

def store_uploaded_file(config, connection, filename, file_size):
    try:
        with open(os.path.join(config['dir_path'], filename),'wb+') as f:
            # すべてのデータの読み書きが終了するまで、クライアントから読み込まれます
            while file_size > 0:
                data = connection.recv(file_size if file_size <= config['stream_rate'] else config['stream_rate'])
                f.write(data)
                file_size -= len(data)

        print('ファイルのアップロードが完了しました。')
        return None

    except Exception as file_err:
        while file_size > 0:
            data = connection.recv(file_size if file_size <= config['stream_rate'] else config['stream_rate'])
            file_size -= len(data)

        error = ErrorInfo('1001', 'ファイル保存中のエラー:' + str(file_err), '解決しない場合は管理者にお問い合わせください。')
        return error

# レスポンスに関係する関数はここから実装
def send_response(connection, filepath, stream_rate):
    # 各処理後にプロセス後のデータを含むレスポンスをクライアントに返す関数
    try:
        with open(filepath, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            f.seek(0, 0)

            # サクセスコード：１（１バイト)とファイルサイズ（８バイト）
            success_header = b'\x01'
            size_header = file_size.to_bytes(8, 'big')
            connection.send(success_header + size_header)

            print(f"処理済みファイル（{file_size}バイト）を送信中")

            # ファイルをstream_rateサイズに分割して送る
            total_sent = 0
            while total_sent < file_size:
                data = f.read(stream_rate)
                if not data:
                    break
                connection.send(data)
                total_sent += len(data)

            print("処理済みファイルの送信完了")
            return None

    except Exception as error:
        print(f"ファイル送信エラー: {str(error)}")
        return ErrorInfo('1004', f'ファイル送信エラー: {str(error)}', 'ネットワーク接続を確認してください。')

def send_error_response(connection, error_info):
    # エラーレスポンスをクライアントに返す関数
    try:
        # エラーコード：０（１バイト）とエラーJSON（ErrorInfoオブジェクト）
        error_header = b'\x00'
        error_json = error_info.to_json()
        error_bytes = error_json.encode('utf-8')

        connection.send(error_header)
        connection.send(len(error_bytes).to_bytes(4, 'big'))
        connection.sendall(error_bytes)

        print(f"エラーレスポンス送信: {error_info.error_code}")

    except Exception as error:
        print(f"エラーレスポンス送信失敗: {str(error)}")

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

# 動画処理などの機能的な関数はここから実装
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

def main():
    config = load_server_config()

    sock = create_server_socket(config)

    while True:
        connection, client_address = sock.accept()
        print(f'{client_address}と接続しました。')

        error = None

        try:
            error = handle_client_request(config, connection)

        except Exception as e:
            error = ErrorInfo('1002', str(e), '解決しない場合は管理者にお問い合わせください。')

        finally:
            inputfile_path = os.path.join(dir_path,filename)
            delete_tmp_files([inputfile_path, output_path])
            if error is not None:
                print(error.to_json())
                send_error_response(connection, error)

            print('コネクションを閉じます')
            connection.close()

if __name__ == '__main__':
    main()
