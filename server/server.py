import socket
import os
import json
import uuid
import subprocess
import sys

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

    except Exception as e:
        print(f"ファイル送信エラー: {str(e)}")
        send_error_response(connection, ErrorInfo('1004', f'ファイル送信エラー: {str(e)}', 'ネットワーク接続を確認してください。'))

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

    except Exception as e:
        print(f"エラーレスポンス送信失敗: {str(e)}")

# 機能的な関数はここから実装
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

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFMPEG エラー: {result.stderr}")
    return output_filename, output_path

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

def get_video_duration(dir_path:str, input_filename:str):
    input_path = os.path.join(dir_path, input_filename)
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'csv=p=0',  # ヘッダーなしで数値のみ
        input_path
    ]
    result = subprocess.run(cmd, capture_output=True)

    return float(result.stdout)


def main():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        server_address = config['server_address']
        server_port = config['server_port']
        max_storage = config['max_storage']
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        dir_path = BASE_DIR + config['storage_dir']
        stream_rate = config['stream_rate']

    # アドレスファミリ : socket.AF_INET, 通信方式 : SOCK_STREAM = TCP通信（信頼性あり、順番保証、コネクション型）
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((server_address, server_port))
    sock.listen(1)
    print('サーバーが起動します。クライアントからの接続を待ちます。')

    while True:
        connection, client_address = sock.accept()
        error = None
        try:
            print('クライアントから接続します。。')
            header = connection.recv(8)
            json_size = int.from_bytes(header[:2], 'big')
            mediatype_size = int.from_bytes(header[2:3], 'big')
            file_size = int.from_bytes(header[3:], 'big')

            req_params = connection.recv(json_size).decode('utf-8')
            mediatype = connection.recv(mediatype_size).decode('utf-8')

            filename = f'{uuid.uuid4().hex}.{mediatype}'

            # ファイルサイズが0の場合はエラーとして扱う
            if file_size <= 0:
                raise Exception('ファイルサイズが無効です')

            try:
                with open(os.path.join(dir_path, filename),'wb+') as f:
                    # すべてのデータの読み書きが終了するまで、クライアントから読み込まれます
                    while file_size > 0:
                        data = connection.recv(file_size if file_size <= stream_rate else stream_rate)
                        f.write(data)
                        file_size -= len(data)
            except Exception as file_err:
                error = ErrorInfo('1001', 'ファイルアップロード中のエラー:' + str(file_err), '解決しない場合は管理者にお問い合わせください。')
                print(str(file_err))
            else:
                print('ファイルのアップロードが完了しました。')

                req_data = json.loads(req_params)
                action = req_data.get('action', 0)

                print(f"受信したアクション: {action}")
                print(f"リクエストは${req_data}")

                match action:
                    case 2:
                        try:
                            processed_filename, output_path = handle_resolution_change(filename, dir_path, req_data)
                            print(f'解像度変更完了: {processed_filename}')
                            send_response(connection, output_path, stream_rate)

                        except Exception as process_err:
                            error = ErrorInfo('1003', f'動画処理中のエラー: {str(process_err)}', 'FFMPEGが正しくインストールされているか確認してください。')
                            print(f"解像度処理エラー: {str(process_err)}")

                    case 5:
                        duration_seconds = get_video_duration(dir_path,filename)
                        if duration_seconds < req_data.get('endseconds'):
                            error = ErrorInfo('1007', '指定した終了時刻が動画の長さを超えています', '指定範囲は動画の時間を超えない値で設定してください')
                            print('指定した終了時刻が動画の長さを超えています。処理を終了します')
                            sys.exit(1)

                        try:
                            processed_filename,output_path = handle_process_video_clip(filename, dir_path, req_data)
                            print(f'時間範囲での動画を作成完了: {processed_filename}')
                            send_response(connection, output_path, stream_rate)
            
                        except Exception as process_err:
                            error = ErrorInfo('1006', f'動画処理中のエラー: {str(process_err)}', 'アップロードした動画を再度確認し、再度トライしてください。')
                            print(f"処理エラー: {str(process_err)}")
                            

        except Exception as e:
            error = ErrorInfo('1002', str(e), '解決しない場合は管理者にお問い合わせください。')
            print(str(e))

        finally:
            if error is not None:
                send_error_response(connection, error)

            print('コネクションを閉じます')
            connection.close()

if __name__ == '__main__':
    main()
